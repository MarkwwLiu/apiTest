"""
Pytest Test File Generator

Auto-generates pytest test files from API definitions.
Produces separate test functions for each HTTP / WSS endpoint
and scenario chains.

Features:
  - Passes auth_config, retry_config, max_response_time to executors
  - Tags as pytest markers for filtering (--tags / --skip-tags)
  - Setup/teardown for scenarios
  - File upload support
  - JSON report generation via conftest
"""

import os

from jinja2 import Template

from ..core.api_parser import ApiTestConfig, AuthConfig, RetryConfig

# ── Jinja2 custom filters ────────────────────────────────────


def _to_python_repr(value):
    """Convert a value to its Python repr (handles None, bool, dict, list)."""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    return repr(value)


# ── Template: conftest.py (shared fixtures + JSON report) ─────

CONFTEST_TEMPLATE = Template('''\
"""
Auto-generated conftest.py
Provides shared fixtures and JSON report generation.
"""

import json
import logging
import os
import time

import pytest

# ── Logging setup ─────────────────────────────────────────────

log_level = os.environ.get("API_TEST_LOG_LEVEL", "WARNING").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.WARNING),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)


# ── JSON Report ──────────────────────────────────────────────

_results = []


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        _results.append({
            "test": item.nodeid,
            "outcome": report.outcome,
            "duration": round(report.duration, 3),
            "tags": [m.name for m in item.iter_markers()],
        })


def pytest_sessionfinish(session, exitstatus):
    report_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "report.json")
    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(_results),
        "passed": sum(1 for r in _results if r["outcome"] == "passed"),
        "failed": sum(1 for r in _results if r["outcome"] == "failed"),
        "skipped": sum(1 for r in _results if r["outcome"] == "skipped"),
        "results": _results,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
''')


# ── Template: HTTP tests ──────────────────────────────────────

HTTP_TEST_TEMPLATE = Template('''\
"""
Auto-generated API test file.
Suite: {{ config.name }}
Base URL: {{ config.base_url }}
HTTP endpoints: {{ config.http_endpoints | length }}
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_test.executors.http_executor import HttpExecutor
{% if config.test_data_file %}
from api_test.core.test_data_loader import DataLoader
{% endif %}

BASE_URL = "{{ config.base_url }}"
DEFAULT_HEADERS = {{ config.default_headers | tojson }}
{% if auth_config %}
AUTH_CONFIG = {{ auth_config }}
{% else %}
AUTH_CONFIG = None
{% endif %}
{% if config.test_data_file %}
_loader = DataLoader(data_dir=os.path.join(os.path.dirname(__file__), "..", "test_data"))
_test_data = _loader.load("{{ config.test_data_file }}")
{% endif %}


@pytest.fixture(scope="module")
def http():
    executor = HttpExecutor(BASE_URL, DEFAULT_HEADERS, auth_config=AUTH_CONFIG)
    yield executor
    executor.close()

{% if config.test_data_file %}
@pytest.fixture
def test_data():
    return _test_data
{% endif %}

{% for ep in config.http_endpoints %}
# ── {{ ep.name }} ─────────────────────────────────────────────

{% for tag in ep.tags %}
@pytest.mark.{{ tag }}
{% endfor %}
{% if config.test_data_file and ep.body %}
@pytest.mark.parametrize("data_record", _test_data, ids=[d.get("name", str(i)) for i, d in enumerate(_test_data)])
def test_{{ ep.name | replace(" ", "_") | replace("-", "_") | lower }}(http, data_record):
    """{{ ep.method }} {{ ep.url }}"""
    body = {{ ep.body | tojson }}
    # Merge test data into body
    for key in list(body.keys()):
        if key in data_record:
            body[key] = data_record[key]

    result = http.execute(
        name="{{ ep.name }}",
        url="{{ ep.url }}",
        method="{{ ep.method }}",
        headers={{ ep.headers | tojson }},
{% if ep.query_params %}
        query_params={{ ep.query_params | tojson }},
{% endif %}
        body=body,
        content_type="{{ ep.content_type }}",
        expected_status={{ ep.expected_status }},
{% if ep.expected_body %}
        expected_body={{ ep.expected_body | tojson }},
{% endif %}
{% if ep.expected_headers %}
        expected_headers={{ ep.expected_headers | tojson }},
{% endif %}
{% if ep.max_response_time %}
        max_response_time={{ ep.max_response_time }},
{% endif %}
        timeout={{ ep.timeout }},
{% if ep.retry %}
        retry_config={{ retry_dict(ep.retry) }},
{% endif %}
{% if ep.upload_files %}
        upload_files={{ ep.upload_files | tojson }},
{% endif %}
        allow_redirects={{ ep.allow_redirects | tojson }},
    )
    assert result.passed, f"FAILED {{ ep.name }}: {result.errors}"
{% else %}
def test_{{ ep.name | replace(" ", "_") | replace("-", "_") | lower }}(http):
    """{{ ep.method }} {{ ep.url }}"""
{% if ep.body %}
    body = {{ ep.body | tojson }}
{% endif %}
    result = http.execute(
        name="{{ ep.name }}",
        url="{{ ep.url }}",
        method="{{ ep.method }}",
        headers={{ ep.headers | tojson }},
{% if ep.query_params %}
        query_params={{ ep.query_params | tojson }},
{% endif %}
{% if ep.body %}
        body=body,
{% endif %}
        content_type="{{ ep.content_type }}",
        expected_status={{ ep.expected_status }},
{% if ep.expected_body %}
        expected_body={{ ep.expected_body | tojson }},
{% endif %}
{% if ep.expected_headers %}
        expected_headers={{ ep.expected_headers | tojson }},
{% endif %}
{% if ep.max_response_time %}
        max_response_time={{ ep.max_response_time }},
{% endif %}
        timeout={{ ep.timeout }},
{% if ep.retry %}
        retry_config={{ retry_dict(ep.retry) }},
{% endif %}
{% if ep.upload_files %}
        upload_files={{ ep.upload_files | tojson }},
{% endif %}
        allow_redirects={{ ep.allow_redirects | tojson }},
    )
    assert result.passed, f"FAILED {{ ep.name }}: {result.errors}"
{% endif %}

{% endfor %}
''')

# ── Template: WSS tests ──────────────────────────────────────

WSS_TEST_TEMPLATE = Template('''\
"""
Auto-generated WebSocket test file.
Suite: {{ config.name }}
WSS endpoints: {{ config.wss_endpoints | length }}
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_test.executors.wss_executor import WssExecutor


@pytest.fixture(scope="module")
def wss():
    return WssExecutor()

{% for ep in config.wss_endpoints %}
# ── {{ ep.name }} ─────────────────────────────────────────────

{% for tag in ep.tags %}
@pytest.mark.{{ tag }}
{% endfor %}
def test_{{ ep.name | replace(" ", "_") | replace("-", "_") | lower }}(wss):
    """WSS {{ ep.url }}"""
    messages = {{ ep.messages | map(attribute="__dict__") | list | tojson }}

    result = wss.execute(
        name="{{ ep.name }}",
        url="{{ ep.url }}",
        headers={{ ep.headers | tojson }},
        messages=messages,
        timeout={{ ep.timeout }},
{% if ep.retry %}
        retry_config={{ retry_dict(ep.retry) }},
{% endif %}
    )
    assert result.connected, f"WSS connection failed: {result.errors}"
    assert result.passed, f"FAILED {{ ep.name }}: {result.errors}"

{% endfor %}
''')

# ── Template: Scenario tests ─────────────────────────────────

SCENARIO_TEST_TEMPLATE = Template('''\
"""
Auto-generated scenario (multi-API chain) test file.
Suite: {{ config.name }}
Scenarios: {{ config.scenarios | length }}
"""

import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_test.executors.http_executor import HttpExecutor
from api_test.executors.wss_executor import WssExecutor

BASE_URL = "{{ config.base_url }}"
DEFAULT_HEADERS = {{ config.default_headers | tojson }}
{% if auth_config %}
AUTH_CONFIG = {{ auth_config }}
{% else %}
AUTH_CONFIG = None
{% endif %}

# Endpoint registry (name -> definition)
HTTP_ENDPOINTS = json.loads(\'\'\'{{ http_endpoints_dict | tojson }}\'\'\')
WSS_ENDPOINTS = json.loads(\'\'\'{{ wss_endpoints_dict | tojson }}\'\'\')


def _resolve_value(template_str, context):
    """Replace {var_name} placeholders with values from context."""
    if not isinstance(template_str, str):
        return template_str
    def replacer(match):
        key = match.group(1)
        return str(context.get(key, match.group(0)))
    return re.sub(r"\\{(\\w+)\\}", replacer, template_str)


def _extract_json_path(data, path):
    """Simple dot-notation JSON path extractor. e.g. \'data.id\'"""
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


def _run_steps(steps, http, context, label=""):
    """Execute a list of scenario steps."""
    for i, step_def in enumerate(steps, 1):
        ep_name = step_def["endpoint_ref"]
        if ep_name not in HTTP_ENDPOINTS:
            continue
        ep = HTTP_ENDPOINTS[ep_name]
        body = step_def.get("override_body") or ep.get("body")
        params = step_def.get("override_params") or ep.get("query_params", {})
        headers = {**ep.get("headers", {}), **(step_def.get("override_headers") or {})}
        url = _resolve_value(ep["url"], context)
        if body and isinstance(body, dict):
            body = {k: _resolve_value(v, context) for k, v in body.items()}
        if params and isinstance(params, dict):
            params = {k: _resolve_value(v, context) for k, v in params.items()}

        result = http.execute(
            name=f"{label}{step_def[\'name\']}",
            url=url,
            method=ep["method"],
            headers=headers,
            query_params=params or None,
            body=body,
            expected_status=ep.get("expected_status", 200),
            timeout=ep.get("timeout", 30),
        )
        assert result.passed, f"{label}{step_def[\'name\']} failed: {result.errors}"

        if step_def.get("save"):
            for var, path in step_def["save"].items():
                context[var] = _extract_json_path(result.response_body, path)


@pytest.fixture(scope="module")
def http():
    executor = HttpExecutor(BASE_URL, DEFAULT_HEADERS, auth_config=AUTH_CONFIG)
    yield executor
    executor.close()


@pytest.fixture(scope="module")
def wss():
    return WssExecutor()

{% for scenario in config.scenarios %}
# ── Scenario: {{ scenario.name }} ────────────────────────────

{% for tag in scenario.tags %}
@pytest.mark.{{ tag }}
{% endfor %}
def test_scenario_{{ scenario.name | replace(" ", "_") | replace("-", "_") | lower }}(http, wss):
    """Scenario: {{ scenario.name }}"""
    context = {}
{% if scenario.setup %}
    # ── Setup ──
    setup_steps = json.loads(\'\'\'{{ scenario.setup | map(attribute="__dict__") | list | tojson }}\'\'\')
    _run_steps(setup_steps, http, context, label="[Setup] ")
{% endif %}

    try:
{% for step in scenario.steps %}
{% set step_idx = loop.index %}

        # Step {{ step_idx }}: {{ step.name }}
{% if step.endpoint_ref in http_endpoint_names %}
        ep_{{ step_idx }} = HTTP_ENDPOINTS["{{ step.endpoint_ref }}"]
{% if step.override_body %}
        body_{{ step_idx }} = {{ step.override_body | tojson }}
{% else %}
        body_{{ step_idx }} = ep_{{ step_idx }}.get("body")
{% endif %}
{% if step.override_params %}
        params_{{ step_idx }} = {{ step.override_params | tojson }}
{% else %}
        params_{{ step_idx }} = ep_{{ step_idx }}.get("query_params", {})
{% endif %}
        headers_{{ step_idx }} = {**ep_{{ step_idx }}.get("headers", {})}
{% if step.override_headers %}
        headers_{{ step_idx }}.update({{ step.override_headers | tojson }})
{% endif %}
        # Resolve placeholders from context
        url_{{ step_idx }} = _resolve_value(ep_{{ step_idx }}["url"], context)
        if body_{{ step_idx }} and isinstance(body_{{ step_idx }}, dict):
            body_{{ step_idx }} = {k: _resolve_value(v, context) for k, v in body_{{ step_idx }}.items()}
        if params_{{ step_idx }} and isinstance(params_{{ step_idx }}, dict):
            params_{{ step_idx }} = {k: _resolve_value(v, context) for k, v in params_{{ step_idx }}.items()}

        result_{{ step_idx }} = http.execute(
            name="{{ step.name }}",
            url=url_{{ step_idx }},
            method=ep_{{ step_idx }}["method"],
            headers=headers_{{ step_idx }},
            query_params=params_{{ step_idx }} or None,
            body=body_{{ step_idx }},
            expected_status=ep_{{ step_idx }}.get("expected_status", 200),
            timeout=ep_{{ step_idx }}.get("timeout", 30),
        )
        assert result_{{ step_idx }}.passed, f"Step {{ step_idx }} ({{ step.name }}) failed: {result_{{ step_idx }}.errors}"
{% if step.save %}
        # Save values to context
{% for var, path in step.save.items() %}
        context["{{ var }}"] = _extract_json_path(result_{{ step_idx }}.response_body, "{{ path }}")
{% endfor %}
{% endif %}
{% endif %}
{% endfor %}
{% if scenario.teardown %}
    finally:
        # ── Teardown ──
        teardown_steps = json.loads(\'\'\'{{ scenario.teardown | map(attribute="__dict__") | list | tojson }}\'\'\')
        _run_steps(teardown_steps, http, context, label="[Teardown] ")
{% else %}
    finally:
        pass
{% endif %}

{% endfor %}
''')


# ── Helper ────────────────────────────────────────────────────


def _retry_to_dict(retry: RetryConfig | None) -> str:
    """Convert RetryConfig to a Python dict repr for code generation."""
    if retry is None:
        return "None"
    return repr({
        "max_retries": retry.max_retries,
        "backoff": retry.backoff,
        "retry_on_status": retry.retry_on_status,
        "retry_on_timeout": retry.retry_on_timeout,
    })


def _auth_to_repr(auth: AuthConfig | None) -> str:
    """Convert AuthConfig to a Python dict repr for code generation."""
    if auth is None:
        return "None"
    d = {
        "type": auth.type,
        "token": auth.token,
        "api_key_header": auth.api_key_header,
        "api_key_value": auth.api_key_value,
        "login_url": auth.login_url,
        "login_method": auth.login_method,
        "login_body": auth.login_body,
        "token_json_path": auth.token_json_path,
    }
    return repr(d)


# ── Public API ────────────────────────────────────────────────


def generate_tests(
    config: ApiTestConfig,
    output_dir: str = "generated_tests",
) -> list[str]:
    """Generate pytest test files from an ApiTestConfig.

    Returns list of generated file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    generated = []
    safe_name = config.name.replace(" ", "_").lower()

    # conftest.py (only once)
    conftest_path = os.path.join(output_dir, "conftest.py")
    if not os.path.exists(conftest_path):
        content = CONFTEST_TEMPLATE.render()
        with open(conftest_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[Generator] conftest   -> {conftest_path}")

    auth_repr = _auth_to_repr(config.auth)

    # HTTP tests
    if config.http_endpoints:
        path = os.path.join(output_dir, f"test_{safe_name}_http.py")
        content = HTTP_TEST_TEMPLATE.render(
            config=config,
            auth_config=auth_repr,
            retry_dict=_retry_to_dict,
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        generated.append(path)
        print(f"[Generator] HTTP tests -> {path}")

    # WSS tests
    if config.wss_endpoints:
        path = os.path.join(output_dir, f"test_{safe_name}_wss.py")
        content = WSS_TEST_TEMPLATE.render(
            config=config,
            retry_dict=_retry_to_dict,
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        generated.append(path)
        print(f"[Generator] WSS tests  -> {path}")

    # Scenario tests
    if config.scenarios:
        http_endpoints_dict = {
            ep.name: {
                "url": ep.url,
                "method": ep.method,
                "headers": ep.headers,
                "query_params": ep.query_params,
                "body": ep.body,
                "expected_status": ep.expected_status,
                "timeout": ep.timeout,
            }
            for ep in config.http_endpoints
        }
        wss_endpoints_dict = {
            ep.name: {
                "url": ep.url,
                "headers": ep.headers,
                "timeout": ep.timeout,
            }
            for ep in config.wss_endpoints
        }
        http_endpoint_names = set(http_endpoints_dict.keys())

        path = os.path.join(output_dir, f"test_{safe_name}_scenario.py")
        content = SCENARIO_TEST_TEMPLATE.render(
            config=config,
            auth_config=auth_repr,
            http_endpoints_dict=http_endpoints_dict,
            wss_endpoints_dict=wss_endpoints_dict,
            http_endpoint_names=http_endpoint_names,
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        generated.append(path)
        print(f"[Generator] Scenario   -> {path}")

    return generated


def generate_all(
    configs: list[ApiTestConfig],
    output_dir: str = "generated_tests",
) -> list[str]:
    """Generate test files for all configs."""
    generated = []
    for config in configs:
        generated.extend(generate_tests(config, output_dir))
    return generated
