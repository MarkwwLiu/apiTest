"""Unit tests for api_test.core.api_parser module."""

import json
import os
import tempfile

import pytest
import yaml

from api_test.core.api_parser import (
    ApiTestConfig,
    AuthConfig,
    HttpEndpoint,
    RetryConfig,
    Scenario,
    ScenarioStep,
    WssEndpoint,
    WssMessage,
    _build_auth,
    _build_config,
    _build_retry,
    _build_scenario_steps,
    _resolve_env,
    parse_api_directory,
    parse_api_file,
)


# ── _resolve_env ──────────────────────────────────────────────


class TestResolveEnv:
    def test_plain_string_unchanged(self):
        assert _resolve_env("hello") == "hello"

    def test_env_var_substitution(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR_123", "resolved_value")
        assert _resolve_env("${TEST_VAR_123}") == "resolved_value"

    def test_env_var_with_default_uses_env(self, monkeypatch):
        monkeypatch.setenv("MY_URL", "https://real.api")
        assert _resolve_env("${MY_URL:-https://fallback.api}") == "https://real.api"

    def test_env_var_with_default_falls_back(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_VAR_XYZ", raising=False)
        assert _resolve_env("${NONEXISTENT_VAR_XYZ:-fallback}") == "fallback"

    def test_env_var_not_found_no_default_kept(self, monkeypatch):
        monkeypatch.delenv("MISSING_VAR_ABC", raising=False)
        assert _resolve_env("${MISSING_VAR_ABC}") == "${MISSING_VAR_ABC}"

    def test_resolve_in_dict(self, monkeypatch):
        monkeypatch.setenv("D_VAR", "val")
        result = _resolve_env({"key": "${D_VAR}", "other": "static"})
        assert result == {"key": "val", "other": "static"}

    def test_resolve_in_list(self, monkeypatch):
        monkeypatch.setenv("L_VAR", "item")
        result = _resolve_env(["${L_VAR}", "fixed"])
        assert result == ["item", "fixed"]

    def test_resolve_nested(self, monkeypatch):
        monkeypatch.setenv("N_VAR", "deep")
        result = _resolve_env({"a": [{"b": "${N_VAR}"}]})
        assert result == {"a": [{"b": "deep"}]}

    def test_non_string_passthrough(self):
        assert _resolve_env(42) == 42
        assert _resolve_env(None) is None
        assert _resolve_env(True) is True

    def test_multiple_vars_in_one_string(self, monkeypatch):
        monkeypatch.setenv("HOST", "localhost")
        monkeypatch.setenv("PORT", "8080")
        assert _resolve_env("${HOST}:${PORT}") == "localhost:8080"


# ── _build_retry ──────────────────────────────────────────────


class TestBuildRetry:
    def test_none_input(self):
        assert _build_retry(None) is None

    def test_defaults(self):
        cfg = _build_retry({})
        assert cfg.max_retries == 0
        assert cfg.backoff == [1.0, 2.0, 4.0]
        assert cfg.retry_on_status == [500, 502, 503, 504]
        assert cfg.retry_on_timeout is True

    def test_custom_values(self):
        cfg = _build_retry({
            "max_retries": 3,
            "backoff": [0.5],
            "retry_on_status": [429],
            "retry_on_timeout": False,
        })
        assert cfg.max_retries == 3
        assert cfg.backoff == [0.5]
        assert cfg.retry_on_status == [429]
        assert cfg.retry_on_timeout is False


# ── _build_auth ───────────────────────────────────────────────


class TestBuildAuth:
    def test_none_input(self):
        assert _build_auth(None) is None

    def test_defaults(self):
        auth = _build_auth({})
        assert auth.type == "none"
        assert auth.token is None
        assert auth.api_key_header == "X-API-Key"

    def test_bearer(self):
        auth = _build_auth({"type": "bearer", "token": "abc123"})
        assert auth.type == "bearer"
        assert auth.token == "abc123"

    def test_api_key(self):
        auth = _build_auth({
            "type": "api_key",
            "api_key_header": "X-Custom",
            "api_key_value": "secret",
        })
        assert auth.api_key_header == "X-Custom"
        assert auth.api_key_value == "secret"

    def test_login(self):
        auth = _build_auth({
            "type": "login",
            "login_url": "/auth",
            "login_method": "POST",
            "login_body": {"user": "admin"},
            "token_json_path": "data.token",
        })
        assert auth.login_url == "/auth"
        assert auth.login_body == {"user": "admin"}
        assert auth.token_json_path == "data.token"


# ── _build_scenario_steps ────────────────────────────────────


class TestBuildScenarioSteps:
    def test_basic_steps(self):
        raw = [
            {"name": "Step 1", "endpoint_ref": "create"},
            {"name": "Step 2", "endpoint_ref": "get", "save": {"id": "data.id"}},
        ]
        steps = _build_scenario_steps(raw)
        assert len(steps) == 2
        assert steps[0].name == "Step 1"
        assert steps[0].endpoint_ref == "create"
        assert steps[0].save is None
        assert steps[1].save == {"id": "data.id"}

    def test_overrides(self):
        raw = [
            {
                "name": "Override step",
                "endpoint_ref": "update",
                "override_body": {"title": "new"},
                "override_params": {"page": 1},
                "override_headers": {"X-Custom": "val"},
            }
        ]
        steps = _build_scenario_steps(raw)
        assert steps[0].override_body == {"title": "new"}
        assert steps[0].override_params == {"page": 1}
        assert steps[0].override_headers == {"X-Custom": "val"}


# ── _build_config ─────────────────────────────────────────────


class TestBuildConfig:
    def test_minimal_config(self):
        raw = {"name": "Test API", "base_url": "https://api.test"}
        config = _build_config(raw)
        assert config.name == "Test API"
        assert config.base_url == "https://api.test"
        assert config.http_endpoints == []
        assert config.wss_endpoints == []
        assert config.scenarios == []

    def test_http_endpoints_with_defaults(self):
        raw = {
            "name": "HTTP Test",
            "base_url": "https://api.test",
            "default_headers": {"Accept": "application/json"},
            "http_endpoints": [
                {"name": "get_users", "url": "/users"},
            ],
        }
        config = _build_config(raw)
        ep = config.http_endpoints[0]
        assert ep.name == "get_users"
        assert ep.method == "GET"
        assert ep.headers == {"Accept": "application/json"}
        assert ep.expected_status == 200
        assert ep.timeout == 30
        assert ep.tags == []

    def test_http_endpoint_custom_values(self):
        raw = {
            "name": "HTTP Test",
            "base_url": "https://api.test",
            "http_endpoints": [
                {
                    "name": "create_item",
                    "url": "/items",
                    "method": "post",
                    "expected_status": 201,
                    "timeout": 15,
                    "body": {"title": "test"},
                    "query_params": {"expand": "true"},
                    "tags": ["create_item", "write"],
                    "expected_body": {"id": "type:int"},
                    "expected_headers": {"x-req-id": "exists:true"},
                    "max_response_time": 5000,
                    "upload_files": {"file": "/tmp/test.txt"},
                    "allow_redirects": False,
                },
            ],
        }
        config = _build_config(raw)
        ep = config.http_endpoints[0]
        assert ep.method == "POST"
        assert ep.expected_status == 201
        assert ep.body == {"title": "test"}
        assert ep.tags == ["create_item", "write"]
        assert ep.max_response_time == 5000
        assert ep.upload_files == {"file": "/tmp/test.txt"}
        assert ep.allow_redirects is False

    def test_http_endpoint_inherits_global_retry(self):
        raw = {
            "name": "Retry Test",
            "base_url": "https://api.test",
            "retry": {"max_retries": 2, "backoff": [1, 2]},
            "http_endpoints": [
                {"name": "ep1", "url": "/test"},
            ],
        }
        config = _build_config(raw)
        assert config.http_endpoints[0].retry.max_retries == 2

    def test_http_endpoint_override_retry(self):
        raw = {
            "name": "Retry Test",
            "base_url": "https://api.test",
            "retry": {"max_retries": 2},
            "http_endpoints": [
                {"name": "ep1", "url": "/test", "retry": {"max_retries": 5}},
            ],
        }
        config = _build_config(raw)
        assert config.http_endpoints[0].retry.max_retries == 5

    def test_wss_endpoints(self):
        raw = {
            "name": "WSS Test",
            "base_url": "wss://ws.test",
            "wss_endpoints": [
                {
                    "name": "echo",
                    "url": "wss://ws.test/echo",
                    "timeout": 15,
                    "tags": ["echo", "wss"],
                    "messages": [
                        {"action": "send", "data": "hello"},
                        {"action": "receive", "timeout": 5, "expected": "hello"},
                    ],
                }
            ],
        }
        config = _build_config(raw)
        assert len(config.wss_endpoints) == 1
        ep = config.wss_endpoints[0]
        assert ep.name == "echo"
        assert len(ep.messages) == 2
        assert ep.messages[0].action == "send"
        assert ep.messages[0].data == "hello"
        assert ep.messages[1].expected == "hello"
        assert ep.messages[1].timeout == 5

    def test_scenarios_with_teardown(self):
        raw = {
            "name": "Scenario Test",
            "base_url": "https://api.test",
            "http_endpoints": [],
            "scenarios": [
                {
                    "name": "flow1",
                    "tags": ["flow1", "scenario"],
                    "steps": [
                        {"name": "Step 1", "endpoint_ref": "create"},
                    ],
                    "teardown": [
                        {"name": "Cleanup", "endpoint_ref": "delete"},
                    ],
                }
            ],
        }
        config = _build_config(raw)
        sc = config.scenarios[0]
        assert sc.name == "flow1"
        assert sc.tags == ["flow1", "scenario"]
        assert len(sc.steps) == 1
        assert sc.setup is None
        assert len(sc.teardown) == 1

    def test_scenarios_with_setup(self):
        raw = {
            "name": "Scenario Test",
            "base_url": "https://api.test",
            "scenarios": [
                {
                    "name": "flow2",
                    "steps": [{"name": "Main", "endpoint_ref": "get"}],
                    "setup": [{"name": "Prep", "endpoint_ref": "create"}],
                }
            ],
        }
        config = _build_config(raw)
        assert config.scenarios[0].setup is not None
        assert len(config.scenarios[0].setup) == 1

    def test_auth_config(self):
        raw = {
            "name": "Auth Test",
            "base_url": "https://api.test",
            "auth": {"type": "bearer", "token": "tok123"},
        }
        config = _build_config(raw)
        assert config.auth.type == "bearer"
        assert config.auth.token == "tok123"

    def test_test_data_file(self):
        raw = {
            "name": "Data Test",
            "base_url": "https://api.test",
            "test_data_file": "posts.yaml",
        }
        config = _build_config(raw)
        assert config.test_data_file == "posts.yaml"

    def test_endpoints_alias(self):
        """Test fallback from 'endpoints' key to 'http_endpoints'."""
        raw = {
            "name": "Alias Test",
            "base_url": "https://api.test",
            "endpoints": [
                {"name": "ep1", "url": "/test"},
            ],
        }
        config = _build_config(raw)
        assert len(config.http_endpoints) == 1

    def test_header_merging(self):
        raw = {
            "name": "Header Test",
            "base_url": "https://api.test",
            "default_headers": {"Accept": "application/json", "X-Default": "yes"},
            "http_endpoints": [
                {"name": "ep1", "url": "/test", "headers": {"X-Default": "overridden", "X-Extra": "new"}},
            ],
        }
        config = _build_config(raw)
        h = config.http_endpoints[0].headers
        assert h["Accept"] == "application/json"
        assert h["X-Default"] == "overridden"
        assert h["X-Extra"] == "new"


# ── parse_api_file ─────────────────────────────────────────────


class TestParseApiFile:
    def test_parse_yaml(self, tmp_path):
        data = {
            "name": "YAML Test",
            "base_url": "https://api.test",
            "http_endpoints": [{"name": "ep1", "url": "/test"}],
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(data), encoding="utf-8")
        config = parse_api_file(str(f))
        assert config.name == "YAML Test"
        assert len(config.http_endpoints) == 1

    def test_parse_json(self, tmp_path):
        data = {
            "name": "JSON Test",
            "base_url": "https://api.test",
            "http_endpoints": [{"name": "ep1", "url": "/test"}],
        }
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        config = parse_api_file(str(f))
        assert config.name == "JSON Test"

    def test_unsupported_format(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("garbage")
        with pytest.raises(ValueError, match="Unsupported file format"):
            parse_api_file(str(f))

    def test_env_var_in_yaml(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TEST_BASE_URL", "https://resolved.api")
        data = {
            "name": "Env Test",
            "base_url": "${TEST_BASE_URL}",
        }
        f = tmp_path / "test.yaml"
        f.write_text(yaml.dump(data), encoding="utf-8")
        config = parse_api_file(str(f))
        assert config.base_url == "https://resolved.api"

    def test_parse_yml_extension(self, tmp_path):
        data = {"name": "YML Test", "base_url": "https://api.test"}
        f = tmp_path / "test.yml"
        f.write_text(yaml.dump(data), encoding="utf-8")
        config = parse_api_file(str(f))
        assert config.name == "YML Test"


# ── parse_api_directory ──────────────────────────────────────


class TestParseApiDirectory:
    def test_parse_multiple_files(self, tmp_path):
        for i, ext in enumerate(["yaml", "json"]):
            data = {"name": f"API {i}", "base_url": f"https://api{i}.test"}
            f = tmp_path / f"api_{i}.{ext}"
            if ext == "yaml":
                f.write_text(yaml.dump(data), encoding="utf-8")
            else:
                f.write_text(json.dumps(data), encoding="utf-8")
        # Also create a .txt file that should be ignored
        (tmp_path / "ignored.txt").write_text("skip me")

        configs = parse_api_directory(str(tmp_path))
        assert len(configs) == 2

    def test_empty_directory(self, tmp_path):
        configs = parse_api_directory(str(tmp_path))
        assert configs == []

    def test_sorted_order(self, tmp_path):
        for name in ["c_api.yaml", "a_api.yaml", "b_api.yaml"]:
            data = {"name": name, "base_url": "https://api.test"}
            (tmp_path / name).write_text(yaml.dump(data), encoding="utf-8")
        configs = parse_api_directory(str(tmp_path))
        assert [c.name for c in configs] == ["a_api.yaml", "b_api.yaml", "c_api.yaml"]
