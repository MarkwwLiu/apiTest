"""Unit tests for api_test.executors.wss_executor module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from api_test.executors.wss_executor import WssExecutor, WssResult, WssStepResult


@pytest.fixture
def executor():
    return WssExecutor()


# ── Connection ────────────────────────────────────────────────


class TestWssConnection:
    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_successful_connection(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test_connect",
            url="wss://echo.test",
            messages=[],
        )
        assert result.connected is True
        assert result.passed is True
        mock_ws.close.assert_called_once()

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_connection_failure(self, mock_create, executor):
        mock_create.side_effect = ConnectionError("refused")
        result = executor.execute(
            name="test_fail",
            url="wss://bad.test",
            messages=[],
        )
        assert result.connected is False
        assert result.passed is False
        assert any("Connection failed" in e for e in result.errors)

    @patch("time.sleep")
    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_connection_retry_success(self, mock_create, mock_sleep, executor):
        mock_ws = MagicMock()
        mock_create.side_effect = [ConnectionError("fail"), mock_ws]
        result = executor.execute(
            name="test_retry",
            url="wss://flaky.test",
            messages=[],
            retry_config={"max_retries": 1, "backoff": [0.1]},
        )
        assert result.connected is True
        assert result.passed is True

    @patch("time.sleep")
    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_connection_retry_exhausted(self, mock_create, mock_sleep, executor):
        mock_create.side_effect = ConnectionError("always fail")
        result = executor.execute(
            name="test_fail",
            url="wss://down.test",
            messages=[],
            retry_config={"max_retries": 2, "backoff": [0.1, 0.2]},
        )
        assert result.connected is False
        assert result.passed is False

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_headers_passed(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_create.return_value = mock_ws
        executor.execute(
            name="test_headers",
            url="wss://echo.test",
            headers={"Authorization": "Bearer tok"},
            messages=[],
        )
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert "Authorization: Bearer tok" in call_kwargs.kwargs.get("header", call_kwargs[1].get("header", []))


# ── Send steps ────────────────────────────────────────────────


class TestWssSend:
    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_send_text(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test_send",
            url="wss://echo.test",
            messages=[{"action": "send", "data": "hello"}],
        )
        mock_ws.send.assert_called_once_with("hello")
        assert result.steps[0].action == "send"
        assert result.steps[0].passed is True

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_send_non_string_converts(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_create.return_value = mock_ws
        executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "send", "data": 42}],
        )
        mock_ws.send.assert_called_once_with("42")

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_send_json(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_create.return_value = mock_ws
        data = {"type": "ping", "id": 1}
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "send_json", "data": data}],
        )
        mock_ws.send.assert_called_once_with(json.dumps(data))
        assert result.steps[0].action == "send_json"
        assert result.steps[0].passed is True

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_send_binary_from_string(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_create.return_value = mock_ws
        executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "send_binary", "data": "hello"}],
        )
        mock_ws.send_binary.assert_called_once_with(b"hello")

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_send_binary_from_list(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_create.return_value = mock_ws
        executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "send_binary", "data": [72, 73]}],
        )
        mock_ws.send_binary.assert_called_once_with(bytes([72, 73]))

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_send_error(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("send failed")
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "send", "data": "x"}],
        )
        assert result.steps[0].passed is False
        assert result.passed is False


# ── Receive steps ─────────────────────────────────────────────


class TestWssReceive:
    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_receive_text_match(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_ws.recv.return_value = "hello"
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "receive", "timeout": 5, "expected": "hello"}],
        )
        assert result.steps[0].passed is True
        assert result.steps[0].data_received == "hello"

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_receive_text_mismatch(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_ws.recv.return_value = "world"
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "receive", "timeout": 5, "expected": "hello"}],
        )
        assert result.steps[0].passed is False

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_receive_no_expected(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_ws.recv.return_value = "anything"
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "receive", "timeout": 5}],
        )
        assert result.steps[0].passed is True

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_receive_error(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_ws.recv.side_effect = TimeoutError("timeout")
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "receive", "timeout": 1}],
        )
        assert result.steps[0].passed is False
        assert "Receive failed" in result.steps[0].error

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_receive_json_match(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_ws.recv.return_value = json.dumps({"type": "pong", "id": 1})
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[
                {"action": "receive_json", "timeout": 5, "expected": {"type": "pong"}},
            ],
        )
        assert result.steps[0].passed is True
        assert result.steps[0].data_received == {"type": "pong", "id": 1}

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_receive_json_mismatch(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_ws.recv.return_value = json.dumps({"type": "error"})
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[
                {"action": "receive_json", "timeout": 5, "expected": {"type": "pong"}},
            ],
        )
        assert result.steps[0].passed is False

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_receive_json_decode_error(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_ws.recv.return_value = "not json"
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "receive_json", "timeout": 5}],
        )
        assert result.steps[0].passed is False
        assert "JSON decode" in result.steps[0].error


# ── Ping / Pong / Wait ───────────────────────────────────────


class TestWssPingPongWait:
    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_ping(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "ping", "data": "keepalive"}],
        )
        mock_ws.ping.assert_called_once_with("keepalive")
        assert result.steps[0].passed is True

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_pong(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "pong", "data": "reply"}],
        )
        mock_ws.pong.assert_called_once_with("reply")
        assert result.steps[0].passed is True

    @patch("time.sleep")
    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_wait(self, mock_create, mock_sleep, executor):
        mock_ws = MagicMock()
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "wait", "timeout": 2}],
        )
        mock_sleep.assert_called_once_with(2)
        assert result.steps[0].passed is True
        assert result.steps[0].action == "wait"

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_unknown_action(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "unknown_action"}],
        )
        assert result.steps[0].passed is False
        assert "Unknown action" in result.steps[0].error


# ── Multi-step / Result fields ────────────────────────────────


class TestWssMultiStep:
    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_multi_step_all_pass(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_ws.recv.return_value = "echo"
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="multi",
            url="wss://echo.test",
            messages=[
                {"action": "send", "data": "hello"},
                {"action": "receive", "timeout": 5, "expected": "echo"},
            ],
        )
        assert len(result.steps) == 2
        assert result.passed is True

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_step_failure_marks_result_failed(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = [None, Exception("fail on second")]
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="partial",
            url="wss://echo.test",
            messages=[
                {"action": "send", "data": "ok"},
                {"action": "send", "data": "fail"},
            ],
        )
        assert result.passed is False
        assert len(result.errors) > 0

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_result_fields(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="fields_test",
            url="wss://echo.test",
            messages=[],
        )
        assert result.endpoint_name == "fields_test"
        assert result.url == "wss://echo.test"
        assert result.elapsed_ms >= 0

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_none_messages(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="no_msgs",
            url="wss://echo.test",
            messages=None,
        )
        assert result.connected is True
        assert result.steps == []

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_ping_error(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_ws.ping.side_effect = Exception("ping failed")
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "ping", "data": "x"}],
        )
        assert result.steps[0].passed is False

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_pong_error(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_ws.pong.side_effect = Exception("pong failed")
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "pong", "data": "x"}],
        )
        assert result.steps[0].passed is False

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_send_json_error(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("json send failed")
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "send_json", "data": {"k": "v"}}],
        )
        assert result.steps[0].passed is False

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_send_binary_error(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_ws.send_binary.side_effect = Exception("binary failed")
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "send_binary", "data": "x"}],
        )
        assert result.steps[0].passed is False

    @patch("api_test.executors.wss_executor.websocket.create_connection")
    def test_receive_json_error(self, mock_create, executor):
        mock_ws = MagicMock()
        mock_ws.recv.side_effect = Exception("recv failed")
        mock_create.return_value = mock_ws
        result = executor.execute(
            name="test",
            url="wss://echo.test",
            messages=[{"action": "receive_json", "timeout": 1}],
        )
        assert result.steps[0].passed is False
        assert "Receive failed" in result.steps[0].error
