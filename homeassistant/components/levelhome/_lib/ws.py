"""WebSocket push client for Level Lock.

This module provides a manager that maintains WebSocket connections to the
partner server for each lock, sending commands and receiving state updates.

It defines explicit message structures for clarity and type safety.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import json
import logging
import random
from typing import Any, Literal

from aiohttp import ClientError, ClientSession, ClientWebSocketResponse, WSMsgType

LOGGER = logging.getLogger(__name__)
from .protocol import coerce_is_locked

# Token provider callable type (async)
TokenProvider = Callable[[], Awaitable[str]]


# =========================
# Message type definitions
# =========================

WsCommandType = Literal["lock", "unlock"]
WsIncomingType = Literal["state", "ack", "error", "pong"]


@dataclass(slots=True)
class WsOutgoingCommand:
    """Command message sent to the partner server over WebSocket.

    Fields:
    - type: always "command"
    - command: "lock" | "unlock"
    - request_id: optional client-generated identifier for correlation
    """

    type: Literal["command"]
    command: WsCommandType
    request_id: str | None = None


@dataclass(slots=True)
class WsIncomingAck:
    """Acknowledgement for a previously sent command.

    Fields:
    - type: always "ack"
    - command: echoed command name
    - status: "accepted" | "rejected"
    - reason: optional rejection reason when status == "rejected"
    - request_id: correlates to WsOutgoingCommand.request_id when provided
    """

    type: Literal["ack"]
    command: WsCommandType
    status: Literal["accepted", "rejected"]
    reason: str | None = None
    request_id: str | None = None


@dataclass(slots=True)
class WsIncomingState:
    """Push state update for a lock.

    Fields:
    - type: always "state"
    - lock_id: identifier of the lock
    - state: "locked" | "unlocked" | other vendor values
    - source: optional origin of the change (e.g. "physical", "digital")
    - updated_at: optional ISO-8601 timestamp
    """

    type: Literal["state"]
    lock_id: str
    state: str
    source: str | None = None
    updated_at: str | None = None


@dataclass(slots=True)
class WsIncomingError:
    """Error message pushed by server.

    Fields:
    - type: always "error"
    - code: vendor-specific error code
    - message: human-readable description
    """

    type: Literal["error"]
    code: str
    message: str


def _coerce_is_locked(state: Any) -> bool | None:
    """Best-effort conversion of vendor state to boolean locked status."""
    if state is None:
        return None
    if isinstance(state, str):
        lowered = state.lower()
        if lowered in ("locked", "lock", "secure"):
            return True
        if lowered in ("unlocked", "unlock", "unsecure"):
            return False
    if isinstance(state, bool):
        return state
    return None


class LevelWebsocketManager:
    """Manage per-lock WebSocket connections and command dispatch."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        get_token: TokenProvider,
        on_state_update: Callable[
            [str, bool | None, dict[str, Any] | None], Awaitable[None]
        ],
    ) -> None:
        self._get_token = get_token
        self._base_url = base_url.rstrip("/")
        self._on_state_update = on_state_update
        self._session: ClientSession = session

        # Runtime state
        self._stop_event = asyncio.Event()
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._sockets: dict[str, ClientWebSocketResponse] = {}
        self._send_locks: dict[str, asyncio.Lock] = {}

    async def async_start(self, lock_ids: list[str]) -> None:
        """Start and maintain connections for the provided locks."""
        for lock_id in lock_ids:
            if lock_id in self._tasks:
                continue
            self._send_locks[lock_id] = asyncio.Lock()
            task = asyncio.create_task(self._run_connection(lock_id))
            self._tasks[lock_id] = task

    async def async_stop(self) -> None:
        """Stop all connections and background tasks."""
        self._stop_event.set()
        # Close sockets first to unblock receivers
        for ws in list(self._sockets.values()):
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass
        self._sockets.clear()
        # Cancel tasks
        for task in list(self._tasks.values()):
            task.cancel()
        self._tasks.clear()

    async def async_send_command(self, lock_id: str, command: WsCommandType) -> None:
        """Send a command over the lock's WebSocket connection.

        If the connection is not established yet, a best-effort attempt will be
        made to connect and then send.
        """

        if lock_id not in self._tasks:
            await self.async_start([lock_id])

        # Ensure a connection is present or connecting
        # Acquire per-lock send lock to serialize sends
        send_lock = self._send_locks.setdefault(lock_id, asyncio.Lock())
        async with send_lock:
            ws = self._sockets.get(lock_id)
            if ws is None or ws.closed:
                # Give the connection loop a chance to connect
                for _ in range(10):
                    await asyncio.sleep(0.2)
                    ws = self._sockets.get(lock_id)
                    if ws is not None and not ws.closed:
                        break
            if ws is None or ws.closed:
                raise ConnectionError(f"WebSocket not connected for lock {lock_id}")

            message = WsOutgoingCommand(type="command", command=command)
            await ws.send_json(message.__dict__)

    async def _run_connection(self, lock_id: str) -> None:
        """Background task to keep a lock WebSocket connected and process messages."""

        backoff_seconds = 1.0
        max_backoff = 30.0
        url = f"{self._base_url}/v1/locks/{lock_id}/ws"

        while not self._stop_event.is_set():
            try:
                token = await self._get_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                }
                LOGGER.debug("Connecting WebSocket for lock %s", lock_id)
                ws = await self._session.ws_connect(url, headers=headers, heartbeat=30)
                self._sockets[lock_id] = ws
                backoff_seconds = 1.0

                async for msg in ws:
                    if msg.type == WSMsgType.TEXT:
                        await self._handle_text_message(lock_id, msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        # Not expected; ignore
                        continue
                    elif msg.type == WSMsgType.CLOSED or msg.type == WSMsgType.ERROR:
                        break
            except asyncio.CancelledError:
                break
            except ClientError as err:
                LOGGER.warning("WebSocket error for lock %s: %s", lock_id, err)
            except Exception as err:
                LOGGER.exception(
                    "Unexpected WebSocket error for lock %s: %s", lock_id, err
                )
            finally:
                ws_ref = self._sockets.pop(lock_id, None)
                if ws_ref is not None and not ws_ref.closed:
                    try:
                        await ws_ref.close()
                    except Exception:  # noqa: BLE001
                        pass

            # Reconnect with backoff
            if self._stop_event.is_set():
                break
            sleep_time = backoff_seconds + random.uniform(0, 0.5)
            LOGGER.debug(
                "Reconnecting WebSocket for lock %s in %.1fs", lock_id, sleep_time
            )
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_time)
                break
            except TimeoutError:
                pass
            backoff_seconds = min(max_backoff, backoff_seconds * 2.0)

    async def _handle_text_message(self, lock_id: str, data: str) -> None:
        """Handle a JSON text message from the server."""
        try:
            payload = json.loads(data)
        except Exception:  # noqa: BLE001
            LOGGER.debug("Non-JSON message for lock %s: %s", lock_id, data)
            return

        msg_type: str | None = payload.get("type")
        if msg_type == "state":
            state = payload.get("state")
            is_locked = coerce_is_locked(state)
            # Pass through entire payload as metadata for future use
            await self._on_state_update(lock_id, is_locked, payload)
            return

        if msg_type == "ack":
            # Acknowledgement to a previously sent command; no action required
            LOGGER.debug("Ack for lock %s: %s", lock_id, payload)
            return

        if msg_type == "error":
            # Server-issued error; log for diagnostics
            code = payload.get("code")
            message = payload.get("message")
            LOGGER.warning(
                "Server error for lock %s: code=%s message=%s", lock_id, code, message
            )
            return

        if msg_type == "pong":
            return

        LOGGER.debug("Unhandled message for lock %s: %s", lock_id, payload)
