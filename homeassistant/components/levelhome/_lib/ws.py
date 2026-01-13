"""WebSocket push client for Level Lock using ws-partner-server protocol.

This module provides a manager that maintains a single WebSocket connection
to the ws-partner-server for all devices on an account.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
import json
import logging
import random
from typing import Any, Literal

from aiohttp import ClientError, ClientSession, ClientWebSocketResponse, WSMsgType

LOGGER = logging.getLogger(__name__)

TokenProvider = Callable[[], Awaitable[str]]

WsCommandType = Literal["lock", "unlock"]


class LevelWebsocketManager:
    """Manage WebSocket connection to ws-partner-server."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        get_token: TokenProvider,
        on_state_update: Callable[
            [str, bool | None, dict[str, Any] | None], Awaitable[None]
        ],
        on_devices_update: Callable[[list[dict[str, Any]]], Awaitable[None]]
        | None = None,
    ) -> None:
        self._get_token = get_token
        self._base_url = base_url.rstrip("/")
        self._on_state_update = on_state_update
        self._on_devices_update = on_devices_update
        self._session: ClientSession = session
        self._stop_event = asyncio.Event()
        self._connected_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._ws: ClientWebSocketResponse | None = None
        self._send_lock = asyncio.Lock()
        self._device_uuid_map: dict[str, str] = {}
        self._devices_list: list[dict[str, Any]] = []
        self._list_devices_event = asyncio.Event()
        self._pending_state_requests: dict[
            str, tuple[asyncio.Event, dict[str, Any] | None]
        ] = {}
        self._pending_commands: dict[str, tuple[asyncio.Event, bool, str | None]] = {}

    async def async_start(self, lock_ids: list[str] | None = None) -> None:
        """Start WebSocket connection."""
        LOGGER.info("Starting WebSocket connection")
        if self._task is None or self._task.done():
            self._stop_event.clear()
            self._connected_event.clear()
            self._list_devices_event.clear()
            self._task = asyncio.create_task(self._run_connection())
            LOGGER.info("WebSocket connection task created, waiting for connection")
            try:
                await asyncio.wait_for(self._connected_event.wait(), timeout=10.0)
                LOGGER.info("WebSocket connected successfully")
            except TimeoutError:
                LOGGER.warning("Timeout waiting for WebSocket connection")
                return
        await self._fetch_device_list()

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Get list of devices via WebSocket."""
        LOGGER.info("Requesting device list via WebSocket")
        self._list_devices_event.clear()
        await self._fetch_device_list()
        try:
            await asyncio.wait_for(self._list_devices_event.wait(), timeout=10.0)
            LOGGER.info("Received device list with %d devices", len(self._devices_list))
        except TimeoutError:
            LOGGER.warning("Timeout waiting for device list response")
        return self._devices_list

    async def async_stop(self) -> None:
        """Stop WebSocket connection and background task."""
        self._stop_event.set()
        self._connected_event.clear()
        if self._ws is not None and not self._ws.closed:
            with suppress(Exception):
                await self._ws.close()
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def register_device_uuid(self, lock_id: str, device_uuid: str) -> None:
        """Register mapping from lock_id to device_uuid."""
        self._device_uuid_map[lock_id] = device_uuid

    async def async_send_command(self, lock_id: str, command: WsCommandType) -> None:
        """Send a lock/unlock command via WebSocket."""
        LOGGER.info("Sending %s command for lock %s", command, lock_id)
        device_uuid = self._device_uuid_map.get(lock_id)
        if device_uuid is None:
            raise ValueError(f"Device UUID not found for lock_id {lock_id}")
        event = asyncio.Event()
        command_key = f"{device_uuid}_{command}"
        self._pending_commands[command_key] = (event, False, None)
        try:
            async with self._send_lock:
                if self._ws is None or self._ws.closed:
                    LOGGER.info("WebSocket not connected, waiting for connection")
                    for _ in range(10):
                        await asyncio.sleep(0.2)
                        if self._ws is not None and not self._ws.closed:
                            break
                    else:
                        LOGGER.error("WebSocket not connected after waiting")
                        raise ConnectionError("WebSocket not connected")
                message = {"type": command, "device_uuid": device_uuid}
                LOGGER.info("Sending WebSocket message: %s", message)
                await self._ws.send_json(message)
            await asyncio.wait_for(event.wait(), timeout=10.0)
            _, success, error = self._pending_commands.get(
                command_key, (None, False, None)
            )
            if not success:
                raise RuntimeError(error or "Command failed")
        except TimeoutError as err:
            LOGGER.warning(
                "Timeout waiting for %s command response for %s", command, device_uuid
            )
            raise TimeoutError(f"Command timeout for {command}") from err
        finally:
            self._pending_commands.pop(command_key, None)

    async def async_get_device_state(self, device_uuid: str) -> dict[str, Any] | None:
        """Get device state via WebSocket."""
        LOGGER.info("Requesting device state for %s", device_uuid)
        event = asyncio.Event()
        self._pending_state_requests[device_uuid] = (event, None)
        try:
            async with self._send_lock:
                if self._ws is None or self._ws.closed:
                    LOGGER.info("WebSocket not connected, waiting for connection")
                    for _ in range(10):
                        await asyncio.sleep(0.2)
                        if self._ws is not None and not self._ws.closed:
                            LOGGER.info("WebSocket connected after waiting")
                            break
                    else:
                        LOGGER.warning(
                            "WebSocket not connected for device state request %s",
                            device_uuid,
                        )
                        return None
                LOGGER.info("Sending get_device_state request for %s", device_uuid)
                await self._ws.send_json(
                    {"type": "get_device_state", "device_uuid": device_uuid}
                )
            LOGGER.info("Waiting for device state response for %s", device_uuid)
            await asyncio.wait_for(event.wait(), timeout=10.0)
            _, result = self._pending_state_requests.get(device_uuid, (None, None))
            LOGGER.info("Received device state for %s: %s", device_uuid, result)
        except TimeoutError:
            LOGGER.warning("Timeout getting state for device %s", device_uuid)
            return None
        else:
            return result
        finally:
            self._pending_state_requests.pop(device_uuid, None)

    async def _fetch_device_list(self) -> None:
        """Fetch device list via WebSocket list_devices message."""
        LOGGER.info("Fetching device list")
        async with self._send_lock:
            if self._ws is None or self._ws.closed:
                LOGGER.warning("Cannot fetch device list - WebSocket not connected")
                return
            LOGGER.info("Sending list_devices request")
            await self._ws.send_json({"type": "list_devices"})

    async def _run_connection(self) -> None:
        """Background task to keep WebSocket connected."""
        backoff_seconds = 1.0
        max_backoff = 30.0
        url = f"{self._base_url}/v1/ws"
        while not self._stop_event.is_set():
            try:
                token = await self._get_token()
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                }
                LOGGER.debug("Connecting WebSocket to %s", url)
                ws = await self._session.ws_connect(url, headers=headers, heartbeat=30)
                self._ws = ws
                backoff_seconds = 1.0
                LOGGER.info("WebSocket connected")
                self._connected_event.set()
                async for msg in ws:
                    if msg.type == WSMsgType.TEXT:
                        await self._handle_text_message(msg.data)
                    elif msg.type in (WSMsgType.CLOSED, WSMsgType.ERROR):
                        break
            except asyncio.CancelledError:
                break
            except ClientError as err:
                LOGGER.warning("WebSocket error: %s", err)
            except Exception:
                LOGGER.exception("Unexpected WebSocket error")
            finally:
                self._connected_event.clear()
                if self._ws is not None and not self._ws.closed:
                    with suppress(Exception):
                        await self._ws.close()
                self._ws = None
            if self._stop_event.is_set():
                break
            sleep_time = backoff_seconds + random.uniform(0, 0.5)
            LOGGER.debug("Reconnecting WebSocket in %.1fs", sleep_time)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_time)
                break
            except TimeoutError:
                pass
            backoff_seconds = min(max_backoff, backoff_seconds * 2.0)

    async def _handle_text_message(self, data: str) -> None:
        """Handle a JSON text message from the server."""
        try:
            payload = json.loads(data)
        except ValueError:
            LOGGER.debug("Non-JSON message: %s", data)
            return
        msg_type: str | None = payload.get("type")
        LOGGER.info("Received WebSocket message type: %s", msg_type)
        if msg_type == "list_devices_reply":
            devices = payload.get("devices", [])
            self._devices_list = devices
            for device in devices:
                device_uuid = device.get("device_uuid") or device.get("uuid")
                if device_uuid:
                    self._device_uuid_map[device_uuid] = device_uuid
            LOGGER.info(
                "Received list_devices_reply with %d devices: %s", len(devices), devices
            )
            self._list_devices_event.set()
            return
        if msg_type == "devices_list_updated":
            devices = payload.get("devices", [])
            self._devices_list = devices
            for device in devices:
                device_uuid = device.get("device_uuid") or device.get("uuid")
                if device_uuid:
                    self._device_uuid_map[device_uuid] = device_uuid
            LOGGER.info(
                "Received devices_list_updated with %d devices: %s",
                len(devices),
                devices,
            )
            if self._on_devices_update is not None:
                await self._on_devices_update(devices)
            return
        if msg_type in ("lock_reply", "unlock_reply"):
            success = payload.get("success")
            device_uuid = payload.get("device_uuid")
            error = payload.get("error")
            LOGGER.info(
                "Received %s: success=%s, device=%s, error=%s",
                msg_type,
                success,
                device_uuid,
                error,
            )
            command = "lock" if msg_type == "lock_reply" else "unlock"
            command_key = f"{device_uuid}_{command}"
            if command_key in self._pending_commands:
                event, _, _ = self._pending_commands[command_key]
                self._pending_commands[command_key] = (event, bool(success), error)
                event.set()
            if not success and error:
                LOGGER.warning(
                    "Command %s failed for device %s: %s", msg_type, device_uuid, error
                )
            return
        if msg_type == "pong":
            return
        if msg_type == "get_device_state_reply":
            device_uuid = payload.get("device_uuid")
            device_state = payload.get("device_state")
            LOGGER.info(
                "Received device state reply for %s: %s", device_uuid, device_state
            )
            if device_uuid and device_uuid in self._pending_state_requests:
                event, _ = self._pending_state_requests[device_uuid]
                self._pending_state_requests[device_uuid] = (event, device_state)
                event.set()
                LOGGER.info("Device state event set for %s", device_uuid)
            elif device_uuid and device_state:
                LOGGER.info("Processing late state reply for %s", device_uuid)
                bolt_state = device_state.get("bolt_state")
                is_locked = None
                state_str = None
                if bolt_state == "Locked":
                    is_locked = True
                    state_str = "locked"
                elif bolt_state == "Unlocked":
                    is_locked = False
                    state_str = "unlocked"
                state_payload = {
                    "state": state_str,
                    "device_uuid": device_uuid,
                    "bolt_state": bolt_state,
                    "battery_level": device_state.get("battery_level"),
                    "reachable": device_state.get("reachable"),
                }
                await self._on_state_update(device_uuid, is_locked, state_payload)
            return
        if msg_type == "device_state_changed":
            device_uuid = payload.get("device_uuid")
            device_state = payload.get("device_state")
            device_name = payload.get("device_name")
            LOGGER.info(
                "Received device state change for %s (%s): %s",
                device_uuid,
                device_name,
                device_state,
            )
            if device_uuid and device_state:
                bolt_state = device_state.get("bolt_state")
                is_locked = None
                state_str = None
                if bolt_state == "Locked":
                    is_locked = True
                    state_str = "locked"
                elif bolt_state == "Unlocked":
                    is_locked = False
                    state_str = "unlocked"
                state_payload = {
                    "state": state_str,
                    "device_uuid": device_uuid,
                    "device_name": device_name,
                    "bolt_state": bolt_state,
                    "battery_level": device_state.get("battery_level"),
                    "reachable": device_state.get("reachable"),
                }
                LOGGER.info(
                    "Processing state change for device %s: bolt_state=%s, is_locked=%s, state=%s",
                    device_uuid,
                    bolt_state,
                    is_locked,
                    state_str,
                )
                await self._on_state_update(device_uuid, is_locked, state_payload)
            return
        LOGGER.info("Unhandled message type: %s, payload: %s", msg_type, payload)
