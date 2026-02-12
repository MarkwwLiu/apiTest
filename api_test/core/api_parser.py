"""
API Definition Parser

Reads API definitions from YAML/JSON files in api_definitions/.
Supports two protocol types:
  - http: REST API endpoints (GET/POST/PUT/PATCH/DELETE)
  - wss:  WebSocket endpoints (connect, send, receive, assert)

Features:
  - Environment variable substitution: ${VAR_NAME} or ${VAR_NAME:-default}
  - Authentication config (bearer, api_key, login flow)
  - Retry config per endpoint
  - Setup/teardown for scenarios
  - Response time assertions
  - Advanced validation (regex, jsonschema, nested)
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

import yaml


# ── Environment variable substitution ─────────────────────────


_ENV_PATTERN = re.compile(r"\$\{(\w+)(?::-(.*?))?\}")


def _resolve_env(value: Any) -> Any:
    """Recursively resolve ${VAR} and ${VAR:-default} in strings, dicts, lists."""
    if isinstance(value, str):
        def _replacer(m: re.Match) -> str:
            var_name = m.group(1)
            default = m.group(2)
            env_val = os.environ.get(var_name)
            if env_val is not None:
                return env_val
            if default is not None:
                return default
            return m.group(0)  # leave as-is if not found and no default
        return _ENV_PATTERN.sub(_replacer, value)
    elif isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env(item) for item in value]
    return value


# ── Authentication ────────────────────────────────────────────


@dataclass
class AuthConfig:
    """Authentication configuration."""

    type: str = "none"  # "none" | "bearer" | "api_key" | "login"
    token: str | None = None  # for bearer: static token or ${ENV_VAR}
    api_key_header: str = "X-API-Key"  # for api_key: header name
    api_key_value: str | None = None  # for api_key: key value
    login_url: str | None = None  # for login: endpoint URL
    login_method: str = "POST"  # for login: HTTP method
    login_body: dict[str, Any] | None = None  # for login: request body
    token_json_path: str = "token"  # for login: JSON path to extract token


# ── Retry Config ──────────────────────────────────────────────


@dataclass
class RetryConfig:
    """Retry configuration for transient failures."""

    max_retries: int = 0
    backoff: list[float] = field(default_factory=lambda: [1.0, 2.0, 4.0])
    retry_on_status: list[int] = field(default_factory=lambda: [500, 502, 503, 504])
    retry_on_timeout: bool = True


# ── HTTP Endpoint ──────────────────────────────────────────────


@dataclass
class HttpEndpoint:
    """A single HTTP API endpoint definition."""

    name: str
    url: str
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, Any] = field(default_factory=dict)
    body: Any | None = None
    content_type: str = "application/json"
    expected_status: int = 200
    expected_body: dict[str, Any] | None = None  # partial json match
    expected_headers: dict[str, str] | None = None
    max_response_time: int | None = None  # ms, None = no assertion
    timeout: int = 30
    tags: list[str] = field(default_factory=list)
    retry: RetryConfig | None = None
    upload_files: dict[str, str] | None = None  # {"field_name": "file_path"}
    allow_redirects: bool = True


# ── WebSocket Endpoint ────────────────────────────────────────


@dataclass
class WssMessage:
    """A single send / receive step inside a WSS test."""

    action: str  # "send" | "receive" | "send_json" | "receive_json" | "send_binary" | "ping" | "pong" | "wait"
    data: Any = None
    timeout: int = 10
    expected: Any = None  # for receive: expected payload (partial match)


@dataclass
class WssEndpoint:
    """A single WebSocket endpoint definition."""

    name: str
    url: str  # ws:// or wss://
    headers: dict[str, str] = field(default_factory=dict)
    messages: list[WssMessage] = field(default_factory=list)
    timeout: int = 30  # connection timeout
    tags: list[str] = field(default_factory=list)
    retry: RetryConfig | None = None


# ── Scenario (multi-API chain) ────────────────────────────────


@dataclass
class ScenarioStep:
    """One step inside a multi-API scenario."""

    name: str
    endpoint_ref: str  # name reference to an HttpEndpoint or WssEndpoint
    save: dict[str, str] | None = None  # {"var_name": "json_path"} to capture from response
    override_body: dict[str, Any] | None = None
    override_params: dict[str, Any] | None = None
    override_headers: dict[str, str] | None = None


@dataclass
class Scenario:
    """Ordered list of steps that share context."""

    name: str
    steps: list[ScenarioStep] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    setup: list[ScenarioStep] | None = None
    teardown: list[ScenarioStep] | None = None


# ── Top-level Config ──────────────────────────────────────────


@dataclass
class ApiTestConfig:
    """Top-level test configuration parsed from one YAML file."""

    name: str
    base_url: str
    http_endpoints: list[HttpEndpoint] = field(default_factory=list)
    wss_endpoints: list[WssEndpoint] = field(default_factory=list)
    scenarios: list[Scenario] = field(default_factory=list)
    default_headers: dict[str, str] = field(default_factory=dict)
    test_data_file: str | None = None
    auth: AuthConfig | None = None
    retry: RetryConfig | None = None  # global default retry


# ── Parsing ───────────────────────────────────────────────────


def parse_api_file(file_path: str) -> ApiTestConfig:
    """Parse a single API definition file (YAML or JSON)."""
    with open(file_path, "r", encoding="utf-8") as f:
        if file_path.endswith((".yaml", ".yml")):
            raw = yaml.safe_load(f)
        elif file_path.endswith(".json"):
            raw = json.load(f)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

    # Resolve environment variables
    raw = _resolve_env(raw)
    return _build_config(raw)


def parse_api_directory(directory: str) -> list[ApiTestConfig]:
    """Parse all API definition files in a directory."""
    configs = []
    for filename in sorted(os.listdir(directory)):
        if filename.endswith((".yaml", ".yml", ".json")):
            filepath = os.path.join(directory, filename)
            configs.append(parse_api_file(filepath))
    return configs


# ── Internal builders ─────────────────────────────────────────


def _build_retry(raw: dict | None) -> RetryConfig | None:
    if raw is None:
        return None
    return RetryConfig(
        max_retries=raw.get("max_retries", 0),
        backoff=raw.get("backoff", [1.0, 2.0, 4.0]),
        retry_on_status=raw.get("retry_on_status", [500, 502, 503, 504]),
        retry_on_timeout=raw.get("retry_on_timeout", True),
    )


def _build_auth(raw: dict | None) -> AuthConfig | None:
    if raw is None:
        return None
    return AuthConfig(
        type=raw.get("type", "none"),
        token=raw.get("token"),
        api_key_header=raw.get("api_key_header", "X-API-Key"),
        api_key_value=raw.get("api_key_value"),
        login_url=raw.get("login_url"),
        login_method=raw.get("login_method", "POST"),
        login_body=raw.get("login_body"),
        token_json_path=raw.get("token_json_path", "token"),
    )


def _build_scenario_steps(raw_steps: list[dict]) -> list[ScenarioStep]:
    steps = []
    for st in raw_steps:
        steps.append(
            ScenarioStep(
                name=st["name"],
                endpoint_ref=st["endpoint_ref"],
                save=st.get("save"),
                override_body=st.get("override_body"),
                override_params=st.get("override_params"),
                override_headers=st.get("override_headers"),
            )
        )
    return steps


def _build_config(raw: dict) -> ApiTestConfig:
    default_headers = raw.get("default_headers", {})
    global_retry = _build_retry(raw.get("retry"))
    auth = _build_auth(raw.get("auth"))

    # HTTP endpoints
    http_endpoints = []
    for ep in raw.get("http_endpoints", raw.get("endpoints", [])):
        merged_headers = {**default_headers, **ep.get("headers", {})}
        ep_retry = _build_retry(ep.get("retry")) or global_retry
        http_endpoints.append(
            HttpEndpoint(
                name=ep["name"],
                url=ep["url"],
                method=ep.get("method", "GET").upper(),
                headers=merged_headers,
                query_params=ep.get("query_params", {}),
                body=ep.get("body"),
                content_type=ep.get("content_type", "application/json"),
                expected_status=ep.get("expected_status", 200),
                expected_body=ep.get("expected_body"),
                expected_headers=ep.get("expected_headers"),
                max_response_time=ep.get("max_response_time"),
                timeout=ep.get("timeout", 30),
                tags=ep.get("tags", []),
                retry=ep_retry,
                upload_files=ep.get("upload_files"),
                allow_redirects=ep.get("allow_redirects", True),
            )
        )

    # WSS endpoints
    wss_endpoints = []
    for ep in raw.get("wss_endpoints", []):
        merged_headers = {**default_headers, **ep.get("headers", {})}
        ep_retry = _build_retry(ep.get("retry")) or global_retry
        messages = []
        for msg in ep.get("messages", []):
            messages.append(
                WssMessage(
                    action=msg["action"],
                    data=msg.get("data"),
                    timeout=msg.get("timeout", 10),
                    expected=msg.get("expected"),
                )
            )
        wss_endpoints.append(
            WssEndpoint(
                name=ep["name"],
                url=ep["url"],
                headers=merged_headers,
                messages=messages,
                timeout=ep.get("timeout", 30),
                tags=ep.get("tags", []),
                retry=ep_retry,
            )
        )

    # Scenarios
    scenarios = []
    for sc in raw.get("scenarios", []):
        steps = _build_scenario_steps(sc.get("steps", []))
        setup = _build_scenario_steps(sc["setup"]) if sc.get("setup") else None
        teardown = _build_scenario_steps(sc["teardown"]) if sc.get("teardown") else None
        scenarios.append(
            Scenario(
                name=sc["name"],
                steps=steps,
                tags=sc.get("tags", []),
                setup=setup,
                teardown=teardown,
            )
        )

    return ApiTestConfig(
        name=raw["name"],
        base_url=raw["base_url"],
        http_endpoints=http_endpoints,
        wss_endpoints=wss_endpoints,
        scenarios=scenarios,
        default_headers=default_headers,
        test_data_file=raw.get("test_data_file"),
        auth=auth,
        retry=global_retry,
    )
