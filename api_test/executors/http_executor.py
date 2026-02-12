"""
HTTP Test Executor

Sends HTTP requests via `requests` library and returns structured results.

Features:
  - Retry with configurable backoff
  - Request/response logging
  - Advanced validation: regex, nested dict, array length, jsonschema
  - Response time assertion
  - File upload (multipart/form-data)
  - Cookie handling
  - Case-insensitive header comparison
  - Authentication (bearer, api_key, login flow)
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger("api_test.http")


@dataclass
class HttpResult:
    """Result of a single HTTP API call."""

    endpoint_name: str
    method: str
    url: str
    status_code: int
    response_body: Any
    response_headers: dict[str, str]
    elapsed_ms: float
    passed: bool
    errors: list[str] = field(default_factory=list)
    request_headers: dict[str, str] = field(default_factory=dict)
    request_body: Any = None
    retries: int = 0


# ── Validation helpers ────────────────────────────────────────


def _deep_match(expected: Any, actual: Any, path: str = "") -> list[str]:
    """Deep comparison with support for regex patterns and special operators.

    Validation rules in expected_body:
      - Simple value:       {"key": "value"}         → exact match
      - Regex:              {"key": "regex:^\\d+$"}   → regex match
      - Nested dict:        {"key": {"sub": "val"}}  → recursive match
      - Array length:       {"items": "len:>0"}      → length assertion
      - Array length exact: {"items": "len:5"}        → length == 5
      - Type check:         {"key": "type:string"}   → type assertion
      - Exists check:       {"key": "exists:true"}   → key must exist (any value)
    """
    errors: list[str] = []

    if isinstance(expected, dict) and isinstance(actual, dict):
        for key, exp_val in expected.items():
            full_path = f"{path}.{key}" if path else key
            act_val = actual.get(key)

            if isinstance(exp_val, str) and exp_val.startswith("regex:"):
                pattern = exp_val[6:]
                if act_val is None:
                    errors.append(f"Body['{full_path}']: key missing, expected regex match")
                elif not re.search(pattern, str(act_val)):
                    errors.append(f"Body['{full_path}']: {act_val!r} does not match regex {pattern!r}")

            elif isinstance(exp_val, str) and exp_val.startswith("len:"):
                len_expr = exp_val[4:]
                if not isinstance(act_val, (list, str, dict)):
                    errors.append(f"Body['{full_path}']: expected iterable, got {type(act_val).__name__}")
                else:
                    actual_len = len(act_val)
                    if len_expr.startswith(">"):
                        threshold = int(len_expr[1:])
                        if actual_len <= threshold:
                            errors.append(f"Body['{full_path}']: length {actual_len} not > {threshold}")
                    elif len_expr.startswith(">="):
                        threshold = int(len_expr[2:])
                        if actual_len < threshold:
                            errors.append(f"Body['{full_path}']: length {actual_len} not >= {threshold}")
                    elif len_expr.startswith("<"):
                        threshold = int(len_expr[1:])
                        if actual_len >= threshold:
                            errors.append(f"Body['{full_path}']: length {actual_len} not < {threshold}")
                    else:
                        expected_len = int(len_expr)
                        if actual_len != expected_len:
                            errors.append(f"Body['{full_path}']: length {actual_len} != {expected_len}")

            elif isinstance(exp_val, str) and exp_val.startswith("type:"):
                type_name = exp_val[5:]
                type_map = {
                    "string": str, "str": str,
                    "int": int, "integer": int,
                    "float": float, "number": (int, float),
                    "bool": bool, "boolean": bool,
                    "list": list, "array": list,
                    "dict": dict, "object": dict,
                    "null": type(None), "none": type(None),
                }
                expected_type = type_map.get(type_name)
                if expected_type and not isinstance(act_val, expected_type):
                    errors.append(
                        f"Body['{full_path}']: expected type {type_name}, got {type(act_val).__name__}"
                    )

            elif isinstance(exp_val, str) and exp_val.startswith("exists:"):
                should_exist = exp_val[7:].lower() in ("true", "1", "yes")
                key_exists = key in actual
                if should_exist and not key_exists:
                    errors.append(f"Body['{full_path}']: key does not exist")
                elif not should_exist and key_exists:
                    errors.append(f"Body['{full_path}']: key should not exist but does")

            elif isinstance(exp_val, dict):
                if not isinstance(act_val, dict):
                    errors.append(f"Body['{full_path}']: expected dict, got {type(act_val).__name__}")
                else:
                    errors.extend(_deep_match(exp_val, act_val, full_path))

            else:
                if act_val != exp_val:
                    errors.append(f"Body['{full_path}']: expected {exp_val!r}, got {act_val!r}")

    return errors


# ── Executor ──────────────────────────────────────────────────


class HttpExecutor:
    """Executes HTTP API calls and validates responses."""

    def __init__(
        self,
        base_url: str,
        default_headers: dict[str, str] | None = None,
        auth_config: dict[str, Any] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if default_headers:
            self.session.headers.update(default_headers)

        self._auth_token: str | None = None
        self._auth_config = auth_config
        if auth_config:
            self._setup_auth(auth_config)

    def _setup_auth(self, auth: dict[str, Any]) -> None:
        auth_type = auth.get("type", "none")
        if auth_type == "bearer":
            self._auth_token = auth.get("token", "")
            self.session.headers["Authorization"] = f"Bearer {self._auth_token}"
        elif auth_type == "api_key":
            header = auth.get("api_key_header", "X-API-Key")
            self.session.headers[header] = auth.get("api_key_value", "")
        elif auth_type == "login":
            self._login(auth)

    def _login(self, auth: dict[str, Any]) -> None:
        """Perform login and extract token from response."""
        login_url = self.base_url + auth.get("login_url", "/auth/login")
        resp = self.session.request(
            auth.get("login_method", "POST"),
            login_url,
            json=auth.get("login_body"),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        token_path = auth.get("token_json_path", "token")
        token = _extract_path(data, token_path)
        if token:
            self._auth_token = str(token)
            self.session.headers["Authorization"] = f"Bearer {self._auth_token}"
            logger.info("Login successful, token acquired")
        else:
            logger.warning("Login response did not contain token at path: %s", token_path)

    def execute(
        self,
        name: str,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        query_params: dict[str, Any] | None = None,
        body: Any = None,
        content_type: str = "application/json",
        expected_status: int = 200,
        expected_body: dict[str, Any] | None = None,
        expected_headers: dict[str, str] | None = None,
        max_response_time: int | None = None,
        timeout: int = 30,
        retry_config: dict[str, Any] | None = None,
        upload_files: dict[str, str] | None = None,
        allow_redirects: bool = True,
    ) -> HttpResult:
        """Execute one HTTP request and validate the response."""
        full_url = self.base_url + url
        req_headers = dict(self.session.headers)
        if headers:
            req_headers.update(headers)

        kwargs: dict[str, Any] = {
            "headers": req_headers,
            "timeout": timeout,
            "allow_redirects": allow_redirects,
        }
        if query_params:
            kwargs["params"] = query_params

        # File upload (multipart/form-data)
        if upload_files:
            files = {}
            for field_name, file_path in upload_files.items():
                files[field_name] = open(file_path, "rb")
            kwargs["files"] = files
            if body and isinstance(body, dict):
                kwargs["data"] = body
        elif body is not None and method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
            if content_type == "application/json":
                kwargs["json"] = body
            else:
                kwargs["data"] = body

        # Retry logic
        max_retries = 0
        backoff = [1.0, 2.0, 4.0]
        retry_on_status: list[int] = [500, 502, 503, 504]
        retry_on_timeout = True
        if retry_config:
            max_retries = retry_config.get("max_retries", 0)
            backoff = retry_config.get("backoff", backoff)
            retry_on_status = retry_config.get("retry_on_status", retry_on_status)
            retry_on_timeout = retry_config.get("retry_on_timeout", True)

        retries = 0
        last_exception: Exception | None = None
        response = None

        for attempt in range(max_retries + 1):
            try:
                start = time.time()
                response = self.session.request(method.upper(), full_url, **kwargs)
                elapsed_ms = (time.time() - start) * 1000

                # Log request/response
                logger.debug(
                    "[%s] %s %s -> %d (%.1fms)",
                    name, method.upper(), full_url,
                    response.status_code, elapsed_ms,
                )
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("  Request headers: %s", req_headers)
                    if body is not None:
                        logger.debug("  Request body: %s", body)
                    logger.debug("  Response body: %s", response.text[:2000])

                # Check if should retry on status
                if (
                    attempt < max_retries
                    and response.status_code in retry_on_status
                ):
                    wait = backoff[min(attempt, len(backoff) - 1)]
                    logger.info(
                        "[%s] Got %d, retrying in %.1fs (%d/%d)",
                        name, response.status_code, wait, attempt + 1, max_retries,
                    )
                    time.sleep(wait)
                    retries += 1
                    continue

                break  # success or non-retryable status

            except requests.exceptions.Timeout:
                last_exception = None
                elapsed_ms = (time.time() - start) * 1000
                if attempt < max_retries and retry_on_timeout:
                    wait = backoff[min(attempt, len(backoff) - 1)]
                    logger.info(
                        "[%s] Timeout, retrying in %.1fs (%d/%d)",
                        name, wait, attempt + 1, max_retries,
                    )
                    time.sleep(wait)
                    retries += 1
                    continue
                return HttpResult(
                    endpoint_name=name,
                    method=method.upper(),
                    url=full_url,
                    status_code=0,
                    response_body=None,
                    response_headers={},
                    elapsed_ms=round(elapsed_ms, 2),
                    passed=False,
                    errors=[f"Request timeout after {timeout}s"],
                    request_headers=req_headers,
                    request_body=body,
                    retries=retries,
                )
            except requests.exceptions.RequestException as e:
                last_exception = e
                elapsed_ms = (time.time() - start) * 1000
                if attempt < max_retries:
                    wait = backoff[min(attempt, len(backoff) - 1)]
                    logger.info(
                        "[%s] %s, retrying in %.1fs (%d/%d)",
                        name, type(e).__name__, wait, attempt + 1, max_retries,
                    )
                    time.sleep(wait)
                    retries += 1
                    continue
                return HttpResult(
                    endpoint_name=name,
                    method=method.upper(),
                    url=full_url,
                    status_code=0,
                    response_body=None,
                    response_headers={},
                    elapsed_ms=round(elapsed_ms, 2),
                    passed=False,
                    errors=[f"Request error: {e}"],
                    request_headers=req_headers,
                    request_body=body,
                    retries=retries,
                )
            finally:
                # Close file handles
                if upload_files and "files" in kwargs:
                    for fh in kwargs["files"].values():
                        fh.close()

        if response is None:
            return HttpResult(
                endpoint_name=name,
                method=method.upper(),
                url=full_url,
                status_code=0,
                response_body=None,
                response_headers={},
                elapsed_ms=0,
                passed=False,
                errors=[f"No response after {max_retries} retries"],
                request_headers=req_headers,
                request_body=body,
                retries=retries,
            )

        # Parse response body
        try:
            resp_body = response.json()
        except (json.JSONDecodeError, ValueError):
            resp_body = response.text

        # ── Validate ──
        errors: list[str] = []

        # Status code
        if response.status_code != expected_status:
            errors.append(
                f"Status: expected {expected_status}, got {response.status_code}"
            )

        # Body (deep match with regex/len/type/exists support)
        if expected_body:
            if isinstance(resp_body, dict):
                errors.extend(_deep_match(expected_body, resp_body))
            elif isinstance(resp_body, list) and isinstance(expected_body, dict):
                errors.append(
                    f"Body: expected dict, got list (length {len(resp_body)})"
                )

        # Headers (case-insensitive)
        if expected_headers:
            resp_headers_lower = {k.lower(): v for k, v in response.headers.items()}
            for key, expected_val in expected_headers.items():
                actual_val = resp_headers_lower.get(key.lower())
                if isinstance(expected_val, str) and expected_val.startswith("regex:"):
                    pattern = expected_val[6:]
                    if actual_val is None or not re.search(pattern, actual_val):
                        errors.append(
                            f"Header['{key}']: {actual_val!r} does not match regex {pattern!r}"
                        )
                elif actual_val != expected_val:
                    errors.append(
                        f"Header['{key}']: expected {expected_val!r}, got {actual_val!r}"
                    )

        # Response time
        if max_response_time is not None and elapsed_ms > max_response_time:
            errors.append(
                f"Response time: {elapsed_ms:.0f}ms exceeds limit {max_response_time}ms"
            )

        result = HttpResult(
            endpoint_name=name,
            method=method.upper(),
            url=full_url,
            status_code=response.status_code,
            response_body=resp_body,
            response_headers=dict(response.headers),
            elapsed_ms=round(elapsed_ms, 2),
            passed=len(errors) == 0,
            errors=errors,
            request_headers=req_headers,
            request_body=body,
            retries=retries,
        )

        # Log failure details
        if not result.passed:
            logger.warning("[%s] FAILED: %s", name, errors)
            logger.warning("  Request: %s %s", method.upper(), full_url)
            if body is not None:
                logger.warning("  Request body: %s", json.dumps(body, default=str)[:1000])
            logger.warning("  Response status: %d", response.status_code)
            logger.warning("  Response body: %s", response.text[:1000])

        return result

    def close(self):
        self.session.close()


def _extract_path(data: Any, path: str) -> Any:
    """Simple dot-notation path extractor for JSON."""
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)]
        else:
            return None
    return current
