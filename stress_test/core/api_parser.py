"""
API Definition Parser

Reads API definitions from YAML/JSON files in api_definitions/ directory.
Each file describes one or more API endpoints with their method, headers,
parameters, body, and expected responses.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class ApiEndpoint:
    """Represents a single API endpoint definition."""

    name: str
    url: str
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, Any] = field(default_factory=dict)
    body: dict[str, Any] | None = None
    content_type: str = "application/json"
    expected_status: int = 200
    timeout: int = 30
    weight: int = 1  # Locust task weight
    tags: list[str] = field(default_factory=list)


@dataclass
class StressTestConfig:
    """Top-level stress test configuration parsed from YAML."""

    name: str
    base_url: str
    endpoints: list[ApiEndpoint]
    default_headers: dict[str, str] = field(default_factory=dict)
    # Stress test parameters
    users: int = 10
    spawn_rate: int = 1
    run_time: str = "1m"
    # Test data file reference (decoupled)
    test_data_file: str | None = None


def parse_api_file(file_path: str) -> StressTestConfig:
    """Parse a single API definition file (YAML or JSON).

    Args:
        file_path: Path to the YAML/JSON API definition file.

    Returns:
        StressTestConfig with all parsed endpoint definitions.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        if file_path.endswith((".yaml", ".yml")):
            raw = yaml.safe_load(f)
        elif file_path.endswith(".json"):
            raw = json.load(f)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

    return _build_config(raw)


def parse_api_directory(directory: str) -> list[StressTestConfig]:
    """Parse all API definition files in a directory.

    Args:
        directory: Path to directory containing API definition files.

    Returns:
        List of StressTestConfig objects.
    """
    configs = []
    for filename in sorted(os.listdir(directory)):
        if filename.endswith((".yaml", ".yml", ".json")):
            filepath = os.path.join(directory, filename)
            configs.append(parse_api_file(filepath))
    return configs


def _build_config(raw: dict) -> StressTestConfig:
    """Build a StressTestConfig from raw parsed dict."""
    default_headers = raw.get("default_headers", {})

    endpoints = []
    for ep_raw in raw.get("endpoints", []):
        merged_headers = {**default_headers, **ep_raw.get("headers", {})}
        endpoint = ApiEndpoint(
            name=ep_raw["name"],
            url=ep_raw["url"],
            method=ep_raw.get("method", "GET").upper(),
            headers=merged_headers,
            query_params=ep_raw.get("query_params", {}),
            body=ep_raw.get("body"),
            content_type=ep_raw.get("content_type", "application/json"),
            expected_status=ep_raw.get("expected_status", 200),
            timeout=ep_raw.get("timeout", 30),
            weight=ep_raw.get("weight", 1),
            tags=ep_raw.get("tags", []),
        )
        endpoints.append(endpoint)

    stress_config = raw.get("stress_config", {})

    return StressTestConfig(
        name=raw["name"],
        base_url=raw["base_url"],
        endpoints=endpoints,
        default_headers=default_headers,
        users=stress_config.get("users", 10),
        spawn_rate=stress_config.get("spawn_rate", 1),
        run_time=stress_config.get("run_time", "1m"),
        test_data_file=raw.get("test_data_file"),
    )
