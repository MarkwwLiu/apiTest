"""
HTTP Test Executor

Sends HTTP requests via `requests` library and returns structured results.
Used by the generated pytest test cases.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any

import requests


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


class HttpExecutor:
    """Executes HTTP API calls and validates responses."""

    def __init__(self, base_url: str, default_headers: dict[str, str] | None = None):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if default_headers:
            self.session.headers.update(default_headers)

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
        timeout: int = 30,
    ) -> HttpResult:
        """Execute one HTTP request and validate the response.

        Args:
            name: Human-readable endpoint name.
            url: Path (appended to base_url).
            method: HTTP method.
            headers: Extra headers for this request.
            query_params: URL query parameters.
            body: Request body (sent as JSON by default).
            content_type: Content-Type header value.
            expected_status: Expected HTTP status code.
            expected_body: Dict of keys/values expected in response JSON.
            expected_headers: Dict of headers expected in response.
            timeout: Request timeout in seconds.

        Returns:
            HttpResult with pass/fail and error details.
        """
        full_url = self.base_url + url
        req_headers = dict(self.session.headers)
        if headers:
            req_headers.update(headers)

        kwargs: dict[str, Any] = {
            "headers": req_headers,
            "timeout": timeout,
        }
        if query_params:
            kwargs["params"] = query_params

        if body is not None and method.upper() in ("POST", "PUT", "PATCH"):
            if content_type == "application/json":
                kwargs["json"] = body
            else:
                kwargs["data"] = body

        start = time.time()
        response = self.session.request(method.upper(), full_url, **kwargs)
        elapsed_ms = (time.time() - start) * 1000

        # Parse response body
        try:
            resp_body = response.json()
        except (json.JSONDecodeError, ValueError):
            resp_body = response.text

        # Validate
        errors: list[str] = []

        if response.status_code != expected_status:
            errors.append(
                f"Status: expected {expected_status}, got {response.status_code}"
            )

        if expected_body and isinstance(resp_body, dict):
            for key, expected_val in expected_body.items():
                actual_val = resp_body.get(key)
                if actual_val != expected_val:
                    errors.append(
                        f"Body['{key}']: expected {expected_val!r}, got {actual_val!r}"
                    )

        if expected_headers:
            for key, expected_val in expected_headers.items():
                actual_val = response.headers.get(key)
                if actual_val != expected_val:
                    errors.append(
                        f"Header['{key}']: expected {expected_val!r}, got {actual_val!r}"
                    )

        return HttpResult(
            endpoint_name=name,
            method=method.upper(),
            url=full_url,
            status_code=response.status_code,
            response_body=resp_body,
            response_headers=dict(response.headers),
            elapsed_ms=round(elapsed_ms, 2),
            passed=len(errors) == 0,
            errors=errors,
        )

    def close(self):
        self.session.close()
