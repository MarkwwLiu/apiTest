"""Unit tests for api_test.executors.http_executor module."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from api_test.executors.http_executor import HttpExecutor, HttpResult, _deep_match, _extract_path


# ══════════════════════════════════════════════════════════════
# _deep_match (validation engine)
# ══════════════════════════════════════════════════════════════


class TestDeepMatchExact:
    def test_exact_match_pass(self):
        assert _deep_match({"id": 1}, {"id": 1}) == []

    def test_exact_match_fail(self):
        errors = _deep_match({"id": 1}, {"id": 2})
        assert len(errors) == 1
        assert "expected 1" in errors[0]

    def test_string_match(self):
        assert _deep_match({"name": "alice"}, {"name": "alice"}) == []

    def test_string_mismatch(self):
        errors = _deep_match({"name": "alice"}, {"name": "bob"})
        assert len(errors) == 1


class TestDeepMatchRegex:
    def test_regex_pass(self):
        assert _deep_match({"id": "regex:^\\d+$"}, {"id": "123"}) == []

    def test_regex_fail(self):
        errors = _deep_match({"id": "regex:^\\d+$"}, {"id": "abc"})
        assert len(errors) == 1
        assert "regex" in errors[0]

    def test_regex_missing_key(self):
        errors = _deep_match({"id": "regex:^\\d+$"}, {"other": "123"})
        assert len(errors) == 1
        assert "missing" in errors[0].lower()


class TestDeepMatchLen:
    def test_len_gt_pass(self):
        assert _deep_match({"items": "len:>0"}, {"items": [1, 2]}) == []

    def test_len_gt_fail(self):
        errors = _deep_match({"items": "len:>0"}, {"items": []})
        assert len(errors) == 1

    def test_len_exact_pass(self):
        assert _deep_match({"items": "len:3"}, {"items": [1, 2, 3]}) == []

    def test_len_exact_fail(self):
        errors = _deep_match({"items": "len:3"}, {"items": [1, 2]})
        assert len(errors) == 1

    def test_len_lt_pass(self):
        assert _deep_match({"items": "len:<5"}, {"items": [1, 2]}) == []

    def test_len_lt_fail(self):
        errors = _deep_match({"items": "len:<2"}, {"items": [1, 2, 3]})
        assert len(errors) == 1

    def test_len_not_iterable(self):
        errors = _deep_match({"items": "len:>0"}, {"items": 42})
        assert len(errors) == 1
        assert "iterable" in errors[0]

    def test_len_on_string(self):
        assert _deep_match({"name": "len:>2"}, {"name": "hello"}) == []

    def test_len_on_dict(self):
        assert _deep_match({"meta": "len:2"}, {"meta": {"a": 1, "b": 2}}) == []


class TestDeepMatchType:
    def test_type_string_pass(self):
        assert _deep_match({"name": "type:string"}, {"name": "hello"}) == []

    def test_type_string_fail(self):
        errors = _deep_match({"name": "type:string"}, {"name": 42})
        assert len(errors) == 1

    def test_type_int_pass(self):
        assert _deep_match({"id": "type:int"}, {"id": 10}) == []

    def test_type_int_fail(self):
        errors = _deep_match({"id": "type:int"}, {"id": "ten"})
        assert len(errors) == 1

    def test_type_float_pass(self):
        assert _deep_match({"val": "type:float"}, {"val": 1.5}) == []

    def test_type_number_pass_int(self):
        assert _deep_match({"val": "type:number"}, {"val": 42}) == []

    def test_type_number_pass_float(self):
        assert _deep_match({"val": "type:number"}, {"val": 3.14}) == []

    def test_type_bool_pass(self):
        assert _deep_match({"flag": "type:bool"}, {"flag": True}) == []

    def test_type_list_pass(self):
        assert _deep_match({"items": "type:list"}, {"items": [1, 2]}) == []

    def test_type_array_alias(self):
        assert _deep_match({"items": "type:array"}, {"items": [1]}) == []

    def test_type_dict_pass(self):
        assert _deep_match({"meta": "type:dict"}, {"meta": {"k": "v"}}) == []

    def test_type_object_alias(self):
        assert _deep_match({"meta": "type:object"}, {"meta": {}}) == []

    def test_type_null_pass(self):
        assert _deep_match({"val": "type:null"}, {"val": None}) == []

    def test_type_none_alias(self):
        assert _deep_match({"val": "type:none"}, {"val": None}) == []

    def test_unknown_type_no_error(self):
        # unknown type name → expected_type is None → no assertion
        assert _deep_match({"val": "type:custom"}, {"val": "anything"}) == []


class TestDeepMatchExists:
    def test_exists_true_pass(self):
        assert _deep_match({"key": "exists:true"}, {"key": "anything"}) == []

    def test_exists_true_fail(self):
        errors = _deep_match({"key": "exists:true"}, {"other": "val"})
        assert len(errors) == 1
        assert "does not exist" in errors[0]

    def test_exists_false_pass(self):
        assert _deep_match({"key": "exists:false"}, {"other": "val"}) == []

    def test_exists_false_fail(self):
        errors = _deep_match({"key": "exists:false"}, {"key": "val"})
        assert len(errors) == 1
        assert "should not exist" in errors[0]

    def test_exists_yes_alias(self):
        assert _deep_match({"key": "exists:yes"}, {"key": None}) == []

    def test_exists_1_alias(self):
        assert _deep_match({"key": "exists:1"}, {"key": ""}) == []


class TestDeepMatchNested:
    def test_nested_dict_pass(self):
        expected = {"user": {"name": "alice", "age": 30}}
        actual = {"user": {"name": "alice", "age": 30, "extra": True}}
        assert _deep_match(expected, actual) == []

    def test_nested_dict_fail(self):
        expected = {"user": {"name": "alice"}}
        actual = {"user": {"name": "bob"}}
        errors = _deep_match(expected, actual)
        assert len(errors) == 1
        assert "user.name" in errors[0]

    def test_nested_not_dict(self):
        expected = {"user": {"name": "alice"}}
        actual = {"user": "not_a_dict"}
        errors = _deep_match(expected, actual)
        assert len(errors) == 1
        assert "expected dict" in errors[0]

    def test_deeply_nested(self):
        expected = {"a": {"b": {"c": 42}}}
        actual = {"a": {"b": {"c": 42}}}
        assert _deep_match(expected, actual) == []

    def test_multiple_errors(self):
        expected = {"a": 1, "b": 2, "c": 3}
        actual = {"a": 10, "b": 20, "c": 3}
        errors = _deep_match(expected, actual)
        assert len(errors) == 2


# ══════════════════════════════════════════════════════════════
# _extract_path
# ══════════════════════════════════════════════════════════════


class TestExtractPath:
    def test_simple_key(self):
        assert _extract_path({"token": "abc"}, "token") == "abc"

    def test_dot_notation(self):
        assert _extract_path({"data": {"id": 42}}, "data.id") == 42

    def test_list_index(self):
        assert _extract_path({"items": [10, 20, 30]}, "items.1") == 20

    def test_nested_list(self):
        data = {"results": [{"id": 1}, {"id": 2}]}
        assert _extract_path(data, "results.0.id") == 1

    def test_missing_key(self):
        assert _extract_path({"a": 1}, "b") is None

    def test_deep_missing(self):
        assert _extract_path({"a": {"b": 1}}, "a.c") is None

    def test_non_dict_path(self):
        assert _extract_path("string", "key") is None


# ══════════════════════════════════════════════════════════════
# HttpExecutor
# ══════════════════════════════════════════════════════════════


class TestHttpExecutorInit:
    def test_base_url_strip_trailing_slash(self):
        executor = HttpExecutor("https://api.test/")
        assert executor.base_url == "https://api.test"

    def test_default_headers_applied(self):
        executor = HttpExecutor(
            "https://api.test",
            default_headers={"Accept": "application/json"},
        )
        assert executor.session.headers.get("Accept") == "application/json"
        executor.close()

    def test_bearer_auth(self):
        executor = HttpExecutor(
            "https://api.test",
            auth_config={"type": "bearer", "token": "mytoken"},
        )
        assert "Bearer mytoken" in executor.session.headers.get("Authorization", "")
        executor.close()

    def test_api_key_auth(self):
        executor = HttpExecutor(
            "https://api.test",
            auth_config={"type": "api_key", "api_key_header": "X-Key", "api_key_value": "secret"},
        )
        assert executor.session.headers.get("X-Key") == "secret"
        executor.close()


class TestHttpExecutorExecute:
    @pytest.fixture
    def executor(self):
        ex = HttpExecutor("https://api.test")
        yield ex
        ex.close()

    def _mock_response(self, status=200, json_data=None, headers=None, elapsed_sec=0.01):
        resp = MagicMock(spec=requests.Response)
        resp.status_code = status
        resp.headers = headers or {"Content-Type": "application/json"}
        resp.text = json.dumps(json_data) if json_data else ""
        resp.json.return_value = json_data
        return resp

    @patch.object(requests.Session, "request")
    def test_simple_get_pass(self, mock_request, executor):
        mock_request.return_value = self._mock_response(
            status=200, json_data={"id": 1}
        )
        result = executor.execute(
            name="get_item",
            url="/items/1",
            method="GET",
            expected_status=200,
        )
        assert result.passed is True
        assert result.status_code == 200
        assert result.errors == []

    @patch.object(requests.Session, "request")
    def test_status_mismatch(self, mock_request, executor):
        mock_request.return_value = self._mock_response(status=404)
        result = executor.execute(
            name="get_item",
            url="/items/999",
            expected_status=200,
        )
        assert result.passed is False
        assert any("Status" in e for e in result.errors)

    @patch.object(requests.Session, "request")
    def test_body_validation(self, mock_request, executor):
        mock_request.return_value = self._mock_response(
            status=200, json_data={"id": 1, "name": "test"}
        )
        result = executor.execute(
            name="get_item",
            url="/items/1",
            expected_status=200,
            expected_body={"id": 1, "name": "type:string"},
        )
        assert result.passed is True

    @patch.object(requests.Session, "request")
    def test_body_validation_failure(self, mock_request, executor):
        mock_request.return_value = self._mock_response(
            status=200, json_data={"id": "not_int"}
        )
        result = executor.execute(
            name="get_item",
            url="/items/1",
            expected_status=200,
            expected_body={"id": "type:int"},
        )
        assert result.passed is False

    @patch.object(requests.Session, "request")
    def test_header_validation_pass(self, mock_request, executor):
        mock_request.return_value = self._mock_response(
            status=200,
            json_data={},
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        result = executor.execute(
            name="check_headers",
            url="/test",
            expected_status=200,
            expected_headers={"content-type": "regex:application/json"},
        )
        assert result.passed is True

    @patch.object(requests.Session, "request")
    def test_header_validation_fail(self, mock_request, executor):
        mock_request.return_value = self._mock_response(
            status=200,
            json_data={},
            headers={"Content-Type": "text/html"},
        )
        result = executor.execute(
            name="check_headers",
            url="/test",
            expected_status=200,
            expected_headers={"content-type": "regex:application/json"},
        )
        assert result.passed is False

    @patch.object(requests.Session, "request")
    def test_header_exact_match_fail(self, mock_request, executor):
        mock_request.return_value = self._mock_response(
            status=200, json_data={}, headers={"X-Custom": "wrong"},
        )
        result = executor.execute(
            name="check_headers",
            url="/test",
            expected_status=200,
            expected_headers={"x-custom": "expected"},
        )
        assert result.passed is False

    @patch.object(requests.Session, "request")
    def test_response_time_pass(self, mock_request, executor):
        mock_request.return_value = self._mock_response(status=200, json_data={})
        result = executor.execute(
            name="fast_ep",
            url="/test",
            expected_status=200,
            max_response_time=10000,
        )
        assert result.passed is True

    @patch.object(requests.Session, "request")
    def test_body_list_when_dict_expected(self, mock_request, executor):
        resp = self._mock_response(status=200, json_data=[1, 2, 3])
        mock_request.return_value = resp
        result = executor.execute(
            name="list_ep",
            url="/test",
            expected_status=200,
            expected_body={"id": 1},
        )
        assert result.passed is False
        assert any("expected dict, got list" in e for e in result.errors)

    @patch.object(requests.Session, "request")
    def test_json_decode_error_returns_text(self, mock_request, executor):
        resp = MagicMock(spec=requests.Response)
        resp.status_code = 200
        resp.headers = {}
        resp.text = "not json"
        resp.json.side_effect = json.JSONDecodeError("err", "doc", 0)
        mock_request.return_value = resp
        result = executor.execute(
            name="text_ep",
            url="/test",
            expected_status=200,
        )
        assert result.response_body == "not json"

    @patch.object(requests.Session, "request")
    def test_post_with_json_body(self, mock_request, executor):
        mock_request.return_value = self._mock_response(
            status=201, json_data={"id": 1}
        )
        result = executor.execute(
            name="create_item",
            url="/items",
            method="POST",
            body={"title": "test"},
            expected_status=201,
        )
        assert result.passed is True
        call_kwargs = mock_request.call_args
        assert "json" in call_kwargs.kwargs or call_kwargs[1].get("json")

    @patch.object(requests.Session, "request")
    def test_post_with_form_body(self, mock_request, executor):
        mock_request.return_value = self._mock_response(status=200, json_data={})
        result = executor.execute(
            name="form_ep",
            url="/form",
            method="POST",
            body={"field": "value"},
            content_type="application/x-www-form-urlencoded",
            expected_status=200,
        )
        assert result.passed is True

    @patch.object(requests.Session, "request")
    def test_query_params(self, mock_request, executor):
        mock_request.return_value = self._mock_response(status=200, json_data={})
        executor.execute(
            name="search",
            url="/search",
            query_params={"q": "test", "page": 1},
            expected_status=200,
        )
        call_kwargs = mock_request.call_args
        assert call_kwargs.kwargs.get("params") == {"q": "test", "page": 1}

    @patch.object(requests.Session, "request")
    def test_timeout_error(self, mock_request, executor):
        mock_request.side_effect = requests.exceptions.Timeout("timed out")
        result = executor.execute(
            name="slow_ep",
            url="/slow",
            timeout=1,
        )
        assert result.passed is False
        assert result.status_code == 0
        assert any("timeout" in e.lower() for e in result.errors)

    @patch.object(requests.Session, "request")
    def test_request_exception(self, mock_request, executor):
        mock_request.side_effect = requests.exceptions.ConnectionError("refused")
        result = executor.execute(
            name="broken_ep",
            url="/broken",
        )
        assert result.passed is False
        assert result.status_code == 0
        assert any("Request error" in e for e in result.errors)

    @patch("time.sleep")
    @patch.object(requests.Session, "request")
    def test_retry_on_status(self, mock_request, mock_sleep, executor):
        fail_resp = self._mock_response(status=500, json_data={})
        ok_resp = self._mock_response(status=200, json_data={})
        mock_request.side_effect = [fail_resp, ok_resp]
        result = executor.execute(
            name="retry_ep",
            url="/retry",
            expected_status=200,
            retry_config={
                "max_retries": 2,
                "backoff": [0.1],
                "retry_on_status": [500],
            },
        )
        assert result.passed is True
        assert result.retries == 1

    @patch("time.sleep")
    @patch.object(requests.Session, "request")
    def test_retry_on_timeout(self, mock_request, mock_sleep, executor):
        mock_request.side_effect = [
            requests.exceptions.Timeout("timed out"),
            self._mock_response(status=200, json_data={}),
        ]
        result = executor.execute(
            name="timeout_retry",
            url="/test",
            expected_status=200,
            retry_config={
                "max_retries": 1,
                "backoff": [0.1],
                "retry_on_timeout": True,
            },
        )
        assert result.passed is True
        assert result.retries == 1

    @patch.object(requests.Session, "request")
    def test_result_fields(self, mock_request, executor):
        mock_request.return_value = self._mock_response(
            status=200, json_data={"ok": True}
        )
        result = executor.execute(
            name="test_ep",
            url="/test",
            method="POST",
            body={"data": 1},
            expected_status=200,
        )
        assert result.endpoint_name == "test_ep"
        assert result.method == "POST"
        assert result.url == "https://api.test/test"
        assert result.request_body == {"data": 1}
        assert result.elapsed_ms >= 0

    @patch.object(requests.Session, "request")
    def test_custom_headers_in_execute(self, mock_request, executor):
        mock_request.return_value = self._mock_response(status=200, json_data={})
        executor.execute(
            name="custom_hdr",
            url="/test",
            headers={"X-Custom": "value"},
            expected_status=200,
        )
        call_kwargs = mock_request.call_args
        assert call_kwargs.kwargs["headers"]["X-Custom"] == "value"


class TestHttpExecutorLogin:
    @patch.object(requests.Session, "request")
    def test_login_auth(self, mock_request):
        login_resp = MagicMock(spec=requests.Response)
        login_resp.status_code = 200
        login_resp.json.return_value = {"token": "login_tok"}
        login_resp.raise_for_status = MagicMock()
        mock_request.return_value = login_resp

        executor = HttpExecutor(
            "https://api.test",
            auth_config={
                "type": "login",
                "login_url": "/auth/login",
                "login_body": {"user": "admin", "pass": "secret"},
                "token_json_path": "token",
            },
        )
        assert "Bearer login_tok" in executor.session.headers.get("Authorization", "")
        executor.close()

    @patch.object(requests.Session, "request")
    def test_login_missing_token(self, mock_request):
        login_resp = MagicMock(spec=requests.Response)
        login_resp.status_code = 200
        login_resp.json.return_value = {"no_token_here": True}
        login_resp.raise_for_status = MagicMock()
        mock_request.return_value = login_resp

        executor = HttpExecutor(
            "https://api.test",
            auth_config={
                "type": "login",
                "login_url": "/auth/login",
                "token_json_path": "token",
            },
        )
        # No token set since path didn't resolve
        assert executor._auth_token is None
        executor.close()
