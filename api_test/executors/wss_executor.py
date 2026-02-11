"""
WebSocket Test Executor

Connects to WSS/WS endpoints, sends and receives messages,
and validates expected responses.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any

import websocket


@dataclass
class WssStepResult:
    """Result of one send/receive step."""

    action: str
    data_sent: Any = None
    data_received: Any = None
    passed: bool = True
    error: str | None = None


@dataclass
class WssResult:
    """Result of a full WebSocket test."""

    endpoint_name: str
    url: str
    connected: bool
    steps: list[WssStepResult] = field(default_factory=list)
    elapsed_ms: float = 0.0
    passed: bool = True
    errors: list[str] = field(default_factory=list)


class WssExecutor:
    """Executes WebSocket API tests."""

    def execute(
        self,
        name: str,
        url: str,
        headers: dict[str, str] | None = None,
        messages: list[dict[str, Any]] | None = None,
        timeout: int = 30,
    ) -> WssResult:
        """Execute a WebSocket test.

        Args:
            name: Human-readable endpoint name.
            url: WebSocket URL (ws:// or wss://).
            headers: Connection headers.
            messages: List of message dicts with keys:
                action: "send" | "receive" | "send_json" | "receive_json"
                data: payload to send (for send actions)
                expected: expected payload (for receive actions)
                timeout: per-message timeout
            timeout: Connection timeout.

        Returns:
            WssResult with step-by-step results.
        """
        result = WssResult(endpoint_name=name, url=url, connected=False)

        if messages is None:
            messages = []

        header_list = None
        if headers:
            header_list = [f"{k}: {v}" for k, v in headers.items()]

        start = time.time()

        try:
            ws = websocket.create_connection(
                url,
                header=header_list,
                timeout=timeout,
            )
            result.connected = True
        except Exception as e:
            result.connected = False
            result.passed = False
            result.errors.append(f"Connection failed: {e}")
            result.elapsed_ms = round((time.time() - start) * 1000, 2)
            return result

        try:
            for msg in messages:
                step = self._execute_step(ws, msg)
                result.steps.append(step)
                if not step.passed:
                    result.passed = False
                    if step.error:
                        result.errors.append(step.error)
        finally:
            ws.close()

        result.elapsed_ms = round((time.time() - start) * 1000, 2)
        return result

    def _execute_step(
        self, ws: websocket.WebSocket, msg: dict[str, Any]
    ) -> WssStepResult:
        """Execute a single send/receive step."""
        action = msg["action"]
        step_timeout = msg.get("timeout", 10)

        if action == "send":
            return self._step_send(ws, msg.get("data", ""))
        elif action == "send_json":
            return self._step_send_json(ws, msg.get("data", {}))
        elif action == "receive":
            return self._step_receive(ws, step_timeout, msg.get("expected"))
        elif action == "receive_json":
            return self._step_receive_json(ws, step_timeout, msg.get("expected"))
        else:
            return WssStepResult(
                action=action, passed=False, error=f"Unknown action: {action}"
            )

    def _step_send(self, ws: websocket.WebSocket, data: Any) -> WssStepResult:
        try:
            payload = data if isinstance(data, str) else str(data)
            ws.send(payload)
            return WssStepResult(action="send", data_sent=payload)
        except Exception as e:
            return WssStepResult(
                action="send", data_sent=data, passed=False, error=str(e)
            )

    def _step_send_json(self, ws: websocket.WebSocket, data: Any) -> WssStepResult:
        try:
            payload = json.dumps(data)
            ws.send(payload)
            return WssStepResult(action="send_json", data_sent=data)
        except Exception as e:
            return WssStepResult(
                action="send_json", data_sent=data, passed=False, error=str(e)
            )

    def _step_receive(
        self, ws: websocket.WebSocket, timeout: int, expected: Any
    ) -> WssStepResult:
        try:
            ws.settimeout(timeout)
            received = ws.recv()
            step = WssStepResult(action="receive", data_received=received)

            if expected is not None and received != str(expected):
                step.passed = False
                step.error = f"Expected {expected!r}, got {received!r}"

            return step
        except Exception as e:
            return WssStepResult(
                action="receive", passed=False, error=str(e)
            )

    def _step_receive_json(
        self, ws: websocket.WebSocket, timeout: int, expected: Any
    ) -> WssStepResult:
        try:
            ws.settimeout(timeout)
            raw = ws.recv()
            received = json.loads(raw)
            step = WssStepResult(action="receive_json", data_received=received)

            if expected is not None and isinstance(expected, dict):
                for key, val in expected.items():
                    actual = received.get(key) if isinstance(received, dict) else None
                    if actual != val:
                        step.passed = False
                        step.error = (
                            f"Key '{key}': expected {val!r}, got {actual!r}"
                        )
                        break

            return step
        except json.JSONDecodeError as e:
            return WssStepResult(
                action="receive_json",
                data_received=raw if "raw" in dir() else None,
                passed=False,
                error=f"JSON decode error: {e}",
            )
        except Exception as e:
            return WssStepResult(
                action="receive_json", passed=False, error=str(e)
            )
