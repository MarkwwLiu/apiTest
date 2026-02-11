"""
API Definition Parser

Reads API definitions from YAML/JSON files in api_definitions/.
Supports two protocol types:
  - http: REST API endpoints (GET/POST/PUT/PATCH/DELETE)
  - wss:  WebSocket endpoints (connect, send, receive, assert)
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any

import yaml


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
    timeout: int = 30
    tags: list[str] = field(default_factory=list)


# ── WebSocket Endpoint ────────────────────────────────────────


@dataclass
class WssMessage:
    """A single send / receive step inside a WSS test."""

    action: str  # "send" | "receive" | "send_json" | "receive_json"
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


# ── Scenario (multi-API chain) ────────────────────────────────


@dataclass
class ScenarioStep:
    """One step inside a multi-API scenario."""

    name: str
    endpoint_ref: str  # name reference to an HttpEndpoint or WssEndpoint
    save: dict[str, str] | None = None  # {"var_name": "json_path"} to capture from response
    override_body: dict[str, Any] | None = None
    override_params: dict[str, Any] | None = None


@dataclass
class Scenario:
    """Ordered list of steps that share context."""

    name: str
    steps: list[ScenarioStep] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


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


def _build_config(raw: dict) -> ApiTestConfig:
    default_headers = raw.get("default_headers", {})

    # HTTP endpoints
    http_endpoints = []
    for ep in raw.get("http_endpoints", raw.get("endpoints", [])):
        merged_headers = {**default_headers, **ep.get("headers", {})}
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
                timeout=ep.get("timeout", 30),
                tags=ep.get("tags", []),
            )
        )

    # WSS endpoints
    wss_endpoints = []
    for ep in raw.get("wss_endpoints", []):
        merged_headers = {**default_headers, **ep.get("headers", {})}
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
            )
        )

    # Scenarios
    scenarios = []
    for sc in raw.get("scenarios", []):
        steps = []
        for st in sc.get("steps", []):
            steps.append(
                ScenarioStep(
                    name=st["name"],
                    endpoint_ref=st["endpoint_ref"],
                    save=st.get("save"),
                    override_body=st.get("override_body"),
                    override_params=st.get("override_params"),
                )
            )
        scenarios.append(
            Scenario(
                name=sc["name"],
                steps=steps,
                tags=sc.get("tags", []),
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
    )
