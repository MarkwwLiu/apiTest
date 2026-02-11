"""
Locust Test File Generator

Auto-generates Locust test files from API definitions.
Supports three modes:
  1. Single API stress test - one endpoint under load
  2. Multi API stress test - multiple endpoints with weighted distribution
  3. Scenario chain test - sequential API calls simulating user flows
"""

import json
import os
from typing import Any

from jinja2 import Template

from ..core.api_parser import ApiEndpoint, StressTestConfig

# ---------------------------------------------------------------------------
# Jinja2 template for the generated Locust test file
# ---------------------------------------------------------------------------
LOCUST_TEMPLATE = Template(
    '''\
"""
Auto-generated Locust stress test file.
Test: {{ config.name }}
Base URL: {{ config.base_url }}
Generated endpoints: {{ config.endpoints | length }}
"""

import json
import os
import sys

from locust import HttpUser, between, task

# Add project root to path so test_data loader is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from stress_test.core.test_data_loader import TestDataLoader

_data_loader = TestDataLoader(data_dir="{{ data_dir }}")

{% if test_data_file %}
# Pre-load test data cycle iterator for this test
_test_data_cycle = _data_loader.get_cycle("{{ test_data_file }}")
{% endif %}


class StressTestUser(HttpUser):
    """Virtual user for stress testing: {{ config.name }}"""

    wait_time = between(1, 3)
{% if default_headers %}
    default_headers = {{ default_headers }}
{% endif %}

{% for ep in config.endpoints %}
    @task({{ ep.weight }})
    def {{ ep.name | replace(" ", "_") | replace("-", "_") | lower }}(self):
        """{{ ep.method }} {{ ep.url }}"""
{% if test_data_file %}
        data_record = next(_test_data_cycle)
{% endif %}
        headers = {{ ep.headers | tojson }}
{% if ep.query_params %}
        params = {{ ep.query_params | tojson }}
{% endif %}
{% if ep.body %}
        body = {{ ep.body | tojson }}
{% if test_data_file %}
        # Merge test data into body if keys overlap
        for key in body:
            if key in data_record:
                body[key] = data_record[key]
{% endif %}
{% endif %}
{% if ep.method == "GET" %}
        with self.client.get(
            "{{ ep.url }}",
            headers=headers,
{% if ep.query_params %}
            params=params,
{% endif %}
            name="{{ ep.name }}",
            timeout={{ ep.timeout }},
            catch_response=True,
        ) as response:
            if response.status_code != {{ ep.expected_status }}:
                response.failure(
                    f"Expected {{ ep.expected_status }}, got {response.status_code}"
                )
{% elif ep.method == "POST" %}
        with self.client.post(
            "{{ ep.url }}",
            headers=headers,
{% if ep.query_params %}
            params=params,
{% endif %}
{% if ep.body %}
            json=body,
{% endif %}
            name="{{ ep.name }}",
            timeout={{ ep.timeout }},
            catch_response=True,
        ) as response:
            if response.status_code != {{ ep.expected_status }}:
                response.failure(
                    f"Expected {{ ep.expected_status }}, got {response.status_code}"
                )
{% elif ep.method == "PUT" %}
        with self.client.put(
            "{{ ep.url }}",
            headers=headers,
{% if ep.query_params %}
            params=params,
{% endif %}
{% if ep.body %}
            json=body,
{% endif %}
            name="{{ ep.name }}",
            timeout={{ ep.timeout }},
            catch_response=True,
        ) as response:
            if response.status_code != {{ ep.expected_status }}:
                response.failure(
                    f"Expected {{ ep.expected_status }}, got {response.status_code}"
                )
{% elif ep.method == "DELETE" %}
        with self.client.delete(
            "{{ ep.url }}",
            headers=headers,
{% if ep.query_params %}
            params=params,
{% endif %}
            name="{{ ep.name }}",
            timeout={{ ep.timeout }},
            catch_response=True,
        ) as response:
            if response.status_code != {{ ep.expected_status }}:
                response.failure(
                    f"Expected {{ ep.expected_status }}, got {response.status_code}"
                )
{% elif ep.method == "PATCH" %}
        with self.client.patch(
            "{{ ep.url }}",
            headers=headers,
{% if ep.query_params %}
            params=params,
{% endif %}
{% if ep.body %}
            json=body,
{% endif %}
            name="{{ ep.name }}",
            timeout={{ ep.timeout }},
            catch_response=True,
        ) as response:
            if response.status_code != {{ ep.expected_status }}:
                response.failure(
                    f"Expected {{ ep.expected_status }}, got {response.status_code}"
                )
{% endif %}

{% endfor %}
'''
)

# ---------------------------------------------------------------------------
# Template for scenario (chained API calls) tests
# ---------------------------------------------------------------------------
SCENARIO_TEMPLATE = Template(
    '''\
"""
Auto-generated Locust scenario (chain) stress test.
Test: {{ config.name }}
Base URL: {{ config.base_url }}
Scenario steps: {{ config.endpoints | length }}
"""

import json
import os
import sys

from locust import HttpUser, between, task

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from stress_test.core.test_data_loader import TestDataLoader

_data_loader = TestDataLoader(data_dir="{{ data_dir }}")

{% if test_data_file %}
_test_data_cycle = _data_loader.get_cycle("{{ test_data_file }}")
{% endif %}


class ScenarioUser(HttpUser):
    """Scenario user that executes API calls in sequence: {{ config.name }}"""

    wait_time = between(1, 3)
{% if default_headers %}
    default_headers = {{ default_headers }}
{% endif %}

    @task
    def run_scenario(self):
        """Execute the full API scenario chain."""
{% if test_data_file %}
        data_record = next(_test_data_cycle)
{% endif %}
        context = {}  # Pass data between steps

{% for ep in config.endpoints %}
        # Step {{ loop.index }}: {{ ep.name }}
        headers_{{ loop.index }} = {{ ep.headers | tojson }}
{% if ep.body %}
        body_{{ loop.index }} = {{ ep.body | tojson }}
{% if test_data_file %}
        for key in body_{{ loop.index }}:
            if key in data_record:
                body_{{ loop.index }}[key] = data_record[key]
{% endif %}
{% endif %}
        with self.client.{{ ep.method | lower }}(
            "{{ ep.url }}",
            headers=headers_{{ loop.index }},
{% if ep.body and ep.method != "GET" %}
            json=body_{{ loop.index }},
{% endif %}
{% if ep.query_params %}
            params={{ ep.query_params | tojson }},
{% endif %}
            name="[Step {{ loop.index }}] {{ ep.name }}",
            timeout={{ ep.timeout }},
            catch_response=True,
        ) as response_{{ loop.index }}:
            if response_{{ loop.index }}.status_code != {{ ep.expected_status }}:
                response_{{ loop.index }}.failure(
                    f"Step {{ loop.index }} failed: expected {{ ep.expected_status }}, got {response_{{ loop.index }}.status_code}"
                )
                return
            try:
                context["step_{{ loop.index }}"] = response_{{ loop.index }}.json()
            except Exception:
                context["step_{{ loop.index }}"] = response_{{ loop.index }}.text

{% endfor %}
'''
)


def generate_locustfile(
    config: StressTestConfig,
    output_dir: str = "generated_tests",
    mode: str = "multi",
) -> str:
    """Generate a Locust test file from an API config.

    Args:
        config: Parsed API stress test configuration.
        output_dir: Directory to write the generated file.
        mode: Test mode - "single", "multi", or "scenario".
              "single" picks the first endpoint only.
              "multi" includes all endpoints with weights.
              "scenario" chains endpoints sequentially.

    Returns:
        Path to the generated Locust file.
    """
    os.makedirs(output_dir, exist_ok=True)

    test_name = config.name.replace(" ", "_").lower()
    filename = f"test_{test_name}_{mode}.py"
    output_path = os.path.join(output_dir, filename)

    data_dir = os.path.abspath("test_data")
    default_headers = repr(config.default_headers) if config.default_headers else None

    if mode == "single":
        # Only use the first endpoint
        single_config = StressTestConfig(
            name=config.name,
            base_url=config.base_url,
            endpoints=[config.endpoints[0]],
            default_headers=config.default_headers,
            users=config.users,
            spawn_rate=config.spawn_rate,
            run_time=config.run_time,
            test_data_file=config.test_data_file,
        )
        rendered = LOCUST_TEMPLATE.render(
            config=single_config,
            data_dir=data_dir,
            default_headers=default_headers,
            test_data_file=config.test_data_file,
        )
    elif mode == "scenario":
        rendered = SCENARIO_TEMPLATE.render(
            config=config,
            data_dir=data_dir,
            default_headers=default_headers,
            test_data_file=config.test_data_file,
        )
    else:
        # multi mode: all endpoints
        rendered = LOCUST_TEMPLATE.render(
            config=config,
            data_dir=data_dir,
            default_headers=default_headers,
            test_data_file=config.test_data_file,
        )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    print(f"[Generator] Generated {mode} test: {output_path}")
    return output_path


def generate_all(
    configs: list[StressTestConfig],
    output_dir: str = "generated_tests",
    modes: list[str] | None = None,
) -> list[str]:
    """Generate test files for all configs and modes.

    Args:
        configs: List of parsed API configs.
        output_dir: Output directory.
        modes: List of modes to generate. Defaults to ["multi"].

    Returns:
        List of generated file paths.
    """
    if modes is None:
        modes = ["multi"]

    generated = []
    for config in configs:
        for mode in modes:
            if mode == "single" and len(config.endpoints) == 0:
                continue
            path = generate_locustfile(config, output_dir, mode)
            generated.append(path)

    return generated
