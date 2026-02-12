"""
WebSocket Test Executor

Connects to WSS/WS endpoints, sends and receives messages,
and validates expected responses.

Features:
  - Text and JSON messages
  - Binary message support (send_binary)
  - Ping/pong actions
  - Wait action (sleep between steps)
  - Retry on connection failure
  - Request/response logging
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import websocket

logger = logging.getLogger("api_test.wss")


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
        retry_config: dict[str, Any] | None = None,
    ) -> WssResult:
        """Execute a WebSocket test.

        Args:
            name: Human-readable endpoint name.
            url: WebSocket URL (ws:// or wss://).
            headers: Connection headers.
            messages: List of message dicts with keys:
                action: "send" | "receive" | "send_json" | "receive_json"
                        | "send_binary" | "ping" | "pong" | "wait"
                data: payload to send (for send actions)
                expected: expected payload (for receive actions)
                timeout: per-message timeout
            timeout: Connection timeout.
            retry_config: Retry configuration dict.

        Returns:
            WssResult with step-by-step results.
        """
        result = WssResult(endpoint_name=name, url=url, connected=False)

        if messages is None:
            messages = []

        header_list = None
        if headers:
            header_list = [f"{k}: {v}" for k, v in headers.items()]

        # Retry logic
        max_retries = 0
        backoff = [1.0, 2.0, 4.0]
        if retry_config:
            max_retries = retry_config.get("max_retries", 0)
            backoff = retry_config.get("backoff", backoff)

        start = time.time()
        ws = None

        for attempt in range(max_retries + 1):
            try:
                ws = websocket.create_connection(
                    url,
                    header=header_list,
                    timeout=timeout,
                )
                result.connected = True
                logger.debug("[%s] Connected to %s", name, url)
                break
            except Exception as e:
                if attempt < max_retries:
                    wait = backoff[min(attempt, len(backoff) - 1)]
                    logger.info(
                        "[%s] Connection failed (%s), retrying in %.1fs (%d/%d)",
                        name, e, wait, attempt + 1, max_retries,
                    )
                    time.sleep(wait)
                    continue
                result.connected = False
                result.passed = False
                result.errors.append(f"Connection failed: {e}")
                result.elapsed_ms = round((time.time() - start) * 1000, 2)
                logger.warning("[%s] Connection failed after %d attempts: %s", name, attempt + 1, e)
                return result

        if ws is None:
            result.passed = False
            result.errors.append("Failed to establish connection")
            return result

        try:
            for msg in messages:
                step = self._execute_step(ws, msg)
                result.steps.append(step)
                logger.debug("[%s] Step %s: passed=%s", name, step.action, step.passed)
                if not step.passed:
                    result.passed = False
                    if step.error:
                        result.errors.append(step.error)
        finally:
            ws.close()

        result.elapsed_ms = round((time.time() - start) * 1000, 2)

        if not result.passed:
            logger.warning("[%s] FAILED: %s", name, result.errors)

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
        elif action == "send_binary":
            return self._step_send_binary(ws, msg.get("data", b""))
        elif action == "receive":
            return self._step_receive(ws, step_timeout, msg.get("expected"))
        elif action == "receive_json":
            return self._step_receive_json(ws, step_timeout, msg.get("expected"))
        elif action == "ping":
            return self._step_ping(ws, msg.get("data", ""))
        elif action == "pong":
            return self._step_pong(ws, msg.get("data", ""))
        elif action == "wait":
            return self._step_wait(msg.get("timeout", 1))
        else:
            return WssStepResult(
                action=action, passed=False, error=f"Unknown action: {action}"
            )

    def _step_send(self, ws: websocket.WebSocket, data: Any) -> WssStepResult:
        try:
            payload = data if isinstance(data, str) else str(data)
            ws.send(payload)
            logger.debug("  -> send: %s", payload[:200])
            return WssStepResult(action="send", data_sent=payload)
        except Exception as e:
            return WssStepResult(
                action="send", data_sent=data, passed=False, error=str(e)
            )

    def _step_send_json(self, ws: websocket.WebSocket, data: Any) -> WssStepResult:
        try:
            payload = json.dumps(data)
            ws.send(payload)
            logger.debug("  -> send_json: %s", payload[:200])
            return WssStepResult(action="send_json", data_sent=data)
        except Exception as e:
            return WssStepResult(
                action="send_json", data_sent=data, passed=False, error=str(e)
            )

    def _step_send_binary(self, ws: websocket.WebSocket, data: Any) -> WssStepResult:
        try:
            if isinstance(data, str):
                payload = data.encode("utf-8")
            elif isinstance(data, list):
                payload = bytes(data)
            else:
                payload = data
            ws.send_binary(payload)
            logger.debug("  -> send_binary: %d bytes", len(payload))
            return WssStepResult(action="send_binary", data_sent=f"<{len(payload)} bytes>")
        except Exception as e:
            return WssStepResult(
                action="send_binary", data_sent=data, passed=False, error=str(e)
            )

    def _step_receive(
        self, ws: websocket.WebSocket, timeout: int, expected: Any
    ) -> WssStepResult:
        try:
            ws.settimeout(timeout)
            received = ws.recv()
            logger.debug("  <- receive: %s", str(received)[:200])
            step = WssStepResult(action="receive", data_received=received)

            if expected is not None and received != str(expected):
                step.passed = False
                step.error = f"Expected {expected!r}, got {received!r}"

            return step
        except Exception as e:
            return WssStepResult(
                action="receive", passed=False, error=f"Receive failed: {e}"
            )

    def _step_receive_json(
        self, ws: websocket.WebSocket, timeout: int, expected: Any
    ) -> WssStepResult:
        raw_data = None
        try:
            ws.settimeout(timeout)
            raw_data = ws.recv()
            received = json.loads(raw_data)
            logger.debug("  <- receive_json: %s", str(received)[:200])
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
                data_received=raw_data,
                passed=False,
                error=f"JSON decode error: {e}",
            )
        except Exception as e:
            return WssStepResult(
                action="receive_json", passed=False, error=f"Receive failed: {e}"
            )

    def _step_ping(self, ws: websocket.WebSocket, data: Any) -> WssStepResult:
        try:
            payload = data if isinstance(data, str) else str(data)
            ws.ping(payload)
            logger.debug("  -> ping: %s", payload[:200])
            return WssStepResult(action="ping", data_sent=payload)
        except Exception as e:
            return WssStepResult(
                action="ping", data_sent=data, passed=False, error=str(e)
            )

    def _step_pong(self, ws: websocket.WebSocket, data: Any) -> WssStepResult:
        try:
            payload = data if isinstance(data, str) else str(data)
            ws.pong(payload)
            logger.debug("  -> pong: %s", payload[:200])
            return WssStepResult(action="pong", data_sent=payload)
        except Exception as e:
            return WssStepResult(
                action="pong", data_sent=data, passed=False, error=str(e)
            )

    def _step_wait(self, duration: float) -> WssStepResult:
        logger.debug("  .. wait: %.1fs", duration)
        time.sleep(duration)
        return WssStepResult(action="wait", data_sent=f"{duration}s")
