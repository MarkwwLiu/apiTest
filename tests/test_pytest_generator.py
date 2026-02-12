"""Unit tests for api_test.generators.pytest_generator module."""

import os

import pytest

from api_test.core.api_parser import (
    ApiTestConfig,
    AuthConfig,
    HttpEndpoint,
    RetryConfig,
    Scenario,
    ScenarioStep,
    WssEndpoint,
    WssMessage,
)
from api_test.generators.pytest_generator import (
    _auth_to_repr,
    _retry_to_dict,
    _to_python_repr,
    generate_all,
    generate_tests,
)


# ── _to_python_repr ───────────────────────────────────────────


class TestToPythonRepr:
    def test_none(self):
        assert _to_python_repr(None) == "None"

    def test_true(self):
        assert _to_python_repr(True) == "True"

    def test_false(self):
        assert _to_python_repr(False) == "False"

    def test_string(self):
        assert _to_python_repr("hello") == "'hello'"

    def test_int(self):
        assert _to_python_repr(42) == "42"

    def test_dict(self):
        result = _to_python_repr({"a": 1})
        assert "a" in result

    def test_list(self):
        result = _to_python_repr([1, 2, 3])
        assert "[1, 2, 3]" in result


# ── _retry_to_dict ────────────────────────────────────────────


class TestRetryToDict:
    def test_none(self):
        assert _retry_to_dict(None) == "None"

    def test_retry_config(self):
        cfg = RetryConfig(max_retries=2, backoff=[1, 2], retry_on_status=[500], retry_on_timeout=True)
        result = _retry_to_dict(cfg)
        assert "'max_retries': 2" in result
        assert "'retry_on_timeout': True" in result
        assert "[500]" in result


# ── _auth_to_repr ─────────────────────────────────────────────


class TestAuthToRepr:
    def test_none(self):
        assert _auth_to_repr(None) == "None"

    def test_bearer(self):
        auth = AuthConfig(type="bearer", token="tok123")
        result = _auth_to_repr(auth)
        assert "'type': 'bearer'" in result
        assert "'token': 'tok123'" in result

    def test_api_key(self):
        auth = AuthConfig(type="api_key", api_key_header="X-Key", api_key_value="sec")
        result = _auth_to_repr(auth)
        assert "'api_key_header': 'X-Key'" in result

    def test_login(self):
        auth = AuthConfig(
            type="login",
            login_url="/auth",
            login_body={"user": "admin"},
            token_json_path="data.token",
        )
        result = _auth_to_repr(auth)
        assert "'login_url': '/auth'" in result
        assert "'token_json_path': 'data.token'" in result


# ── generate_tests: HTTP ──────────────────────────────────────


class TestGenerateTestsHttp:
    def _make_config(self, **kwargs):
        defaults = {
            "name": "Test API",
            "base_url": "https://api.test",
            "http_endpoints": [
                HttpEndpoint(
                    name="list_items",
                    url="/items",
                    method="GET",
                    expected_status=200,
                    tags=["list_items", "read"],
                ),
            ],
        }
        defaults.update(kwargs)
        return ApiTestConfig(**defaults)

    def test_generates_http_file(self, tmp_path):
        config = self._make_config()
        files = generate_tests(config, str(tmp_path))
        assert len(files) == 1
        assert "http" in files[0]
        assert os.path.exists(files[0])

    def test_generated_file_contains_test_function(self, tmp_path):
        config = self._make_config()
        files = generate_tests(config, str(tmp_path))
        content = open(files[0]).read()
        assert "def test_list_items" in content
        assert "HttpExecutor" in content

    def test_conftest_created(self, tmp_path):
        config = self._make_config()
        generate_tests(config, str(tmp_path))
        conftest = os.path.join(str(tmp_path), "conftest.py")
        assert os.path.exists(conftest)

    def test_conftest_not_overwritten(self, tmp_path):
        # Write conftest first
        conftest = os.path.join(str(tmp_path), "conftest.py")
        with open(conftest, "w") as f:
            f.write("# custom conftest\n")
        config = self._make_config()
        generate_tests(config, str(tmp_path))
        content = open(conftest).read()
        assert "# custom conftest" in content

    def test_tags_as_markers(self, tmp_path):
        config = self._make_config()
        files = generate_tests(config, str(tmp_path))
        content = open(files[0]).read()
        assert "@pytest.mark.list_items" in content
        assert "@pytest.mark.read" in content

    def test_with_auth(self, tmp_path):
        config = self._make_config(
            auth=AuthConfig(type="bearer", token="tok"),
        )
        files = generate_tests(config, str(tmp_path))
        content = open(files[0]).read()
        assert "AUTH_CONFIG" in content
        assert "'bearer'" in content

    def test_with_retry(self, tmp_path):
        ep = HttpEndpoint(
            name="retry_ep",
            url="/test",
            retry=RetryConfig(max_retries=3),
            tags=["retry_ep"],
        )
        config = self._make_config(http_endpoints=[ep])
        files = generate_tests(config, str(tmp_path))
        content = open(files[0]).read()
        assert "retry_config" in content

    def test_with_expected_body(self, tmp_path):
        ep = HttpEndpoint(
            name="body_ep",
            url="/test",
            expected_body={"id": "type:int"},
            tags=["body_ep"],
        )
        config = self._make_config(http_endpoints=[ep])
        files = generate_tests(config, str(tmp_path))
        content = open(files[0]).read()
        assert "expected_body" in content

    def test_with_query_params(self, tmp_path):
        ep = HttpEndpoint(
            name="query_ep",
            url="/search",
            query_params={"q": "test"},
            tags=["query_ep"],
        )
        config = self._make_config(http_endpoints=[ep])
        files = generate_tests(config, str(tmp_path))
        content = open(files[0]).read()
        assert "query_params" in content

    def test_with_test_data(self, tmp_path):
        ep = HttpEndpoint(
            name="create_ep",
            url="/items",
            method="POST",
            body={"title": "default"},
            tags=["create_ep", "write"],
        )
        config = self._make_config(
            http_endpoints=[ep],
            test_data_file="items.yaml",
        )
        files = generate_tests(config, str(tmp_path))
        content = open(files[0]).read()
        assert "parametrize" in content
        assert "DataLoader" in content

    def test_with_max_response_time(self, tmp_path):
        ep = HttpEndpoint(
            name="timed_ep",
            url="/test",
            max_response_time=5000,
            tags=["timed_ep"],
        )
        config = self._make_config(http_endpoints=[ep])
        files = generate_tests(config, str(tmp_path))
        content = open(files[0]).read()
        assert "max_response_time=5000" in content

    def test_with_upload_files(self, tmp_path):
        ep = HttpEndpoint(
            name="upload_ep",
            url="/upload",
            method="POST",
            upload_files={"file": "/tmp/test.txt"},
            tags=["upload_ep"],
        )
        config = self._make_config(http_endpoints=[ep])
        files = generate_tests(config, str(tmp_path))
        content = open(files[0]).read()
        assert "upload_files" in content

    def test_allow_redirects_false(self, tmp_path):
        ep = HttpEndpoint(
            name="noredirect_ep",
            url="/test",
            allow_redirects=False,
            tags=["noredirect_ep"],
        )
        config = self._make_config(http_endpoints=[ep])
        files = generate_tests(config, str(tmp_path))
        content = open(files[0]).read()
        assert "allow_redirects=False" in content


# ── generate_tests: WSS ───────────────────────────────────────


class TestGenerateTestsWss:
    def test_generates_wss_file(self, tmp_path):
        config = ApiTestConfig(
            name="WSS API",
            base_url="wss://ws.test",
            wss_endpoints=[
                WssEndpoint(
                    name="echo",
                    url="wss://ws.test/echo",
                    messages=[WssMessage(action="send", data="hi")],
                    tags=["echo", "wss"],
                ),
            ],
        )
        files = generate_tests(config, str(tmp_path))
        assert any("wss" in f for f in files)

    def test_wss_content(self, tmp_path):
        config = ApiTestConfig(
            name="WSS API",
            base_url="wss://ws.test",
            wss_endpoints=[
                WssEndpoint(
                    name="echo_test",
                    url="wss://ws.test/echo",
                    messages=[WssMessage(action="send", data="hello")],
                    tags=["echo_test", "wss"],
                ),
            ],
        )
        files = generate_tests(config, str(tmp_path))
        wss_file = [f for f in files if "wss" in f][0]
        content = open(wss_file).read()
        assert "def test_echo_test" in content
        assert "WssExecutor" in content
        assert "@pytest.mark.echo_test" in content

    def test_wss_with_retry(self, tmp_path):
        config = ApiTestConfig(
            name="WSS API",
            base_url="wss://ws.test",
            wss_endpoints=[
                WssEndpoint(
                    name="retry_echo",
                    url="wss://ws.test/echo",
                    messages=[],
                    tags=["retry_echo"],
                    retry=RetryConfig(max_retries=2),
                ),
            ],
        )
        files = generate_tests(config, str(tmp_path))
        content = open([f for f in files if "wss" in f][0]).read()
        assert "retry_config" in content


# ── generate_tests: Scenario ─────────────────────────────────


class TestGenerateTestsScenario:
    def test_generates_scenario_file(self, tmp_path):
        config = ApiTestConfig(
            name="Scenario API",
            base_url="https://api.test",
            http_endpoints=[
                HttpEndpoint(name="create", url="/items", method="POST"),
                HttpEndpoint(name="get", url="/items/1"),
            ],
            scenarios=[
                Scenario(
                    name="create_flow",
                    steps=[
                        ScenarioStep(name="Create", endpoint_ref="create", save={"id": "id"}),
                        ScenarioStep(name="Get", endpoint_ref="get"),
                    ],
                    tags=["create_flow", "scenario"],
                ),
            ],
        )
        files = generate_tests(config, str(tmp_path))
        # http_endpoints also generate an HTTP test file
        scenario_files = [f for f in files if os.path.basename(f).endswith("_scenario.py")]
        assert len(scenario_files) == 1

    def test_scenario_content(self, tmp_path):
        config = ApiTestConfig(
            name="Scenario API",
            base_url="https://api.test",
            http_endpoints=[
                HttpEndpoint(name="create", url="/items", method="POST"),
            ],
            scenarios=[
                Scenario(
                    name="my_flow",
                    steps=[ScenarioStep(name="Create", endpoint_ref="create")],
                    tags=["my_flow", "scenario"],
                    teardown=[ScenarioStep(name="Cleanup", endpoint_ref="create")],
                ),
            ],
        )
        files = generate_tests(config, str(tmp_path))
        scenario_file = [f for f in files if os.path.basename(f).endswith("_scenario.py")][0]
        content = open(scenario_file).read()
        assert "def test_scenario_my_flow" in content
        assert "teardown" in content.lower()
        assert "@pytest.mark.my_flow" in content


# ── generate_all ──────────────────────────────────────────────


class TestGenerateAll:
    def test_multiple_configs(self, tmp_path):
        config1 = ApiTestConfig(
            name="API One",
            base_url="https://one.test",
            http_endpoints=[HttpEndpoint(name="ep1", url="/one")],
        )
        config2 = ApiTestConfig(
            name="API Two",
            base_url="https://two.test",
            http_endpoints=[HttpEndpoint(name="ep2", url="/two")],
        )
        files = generate_all([config1, config2], str(tmp_path))
        assert len(files) == 2

    def test_empty_configs(self, tmp_path):
        files = generate_all([], str(tmp_path))
        assert files == []

    def test_no_endpoints_no_files(self, tmp_path):
        config = ApiTestConfig(name="Empty", base_url="https://api.test")
        files = generate_tests(config, str(tmp_path))
        assert files == []

    def test_output_dir_created(self, tmp_path):
        out = str(tmp_path / "new_dir")
        config = ApiTestConfig(
            name="Create Dir Test",
            base_url="https://api.test",
            http_endpoints=[HttpEndpoint(name="ep", url="/test")],
        )
        generate_tests(config, out)
        assert os.path.isdir(out)


# ── File naming ───────────────────────────────────────────────


class TestFileNaming:
    def test_safe_name_with_spaces(self, tmp_path):
        config = ApiTestConfig(
            name="My Cool API",
            base_url="https://api.test",
            http_endpoints=[HttpEndpoint(name="ep", url="/test")],
        )
        files = generate_tests(config, str(tmp_path))
        assert "my_cool_api" in files[0]

    def test_http_and_wss_separate_files(self, tmp_path):
        config = ApiTestConfig(
            name="Mixed API",
            base_url="https://api.test",
            http_endpoints=[HttpEndpoint(name="http_ep", url="/test")],
            wss_endpoints=[
                WssEndpoint(name="wss_ep", url="wss://ws.test", messages=[]),
            ],
        )
        files = generate_tests(config, str(tmp_path))
        assert len(files) == 2
        names = [os.path.basename(f) for f in files]
        assert any("http" in n for n in names)
        assert any("wss" in n for n in names)
