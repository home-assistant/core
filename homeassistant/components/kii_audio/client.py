"""Kii Audio plain WebSocket client."""

import asyncio
from collections.abc import Callable
from contextlib import suppress
import copy
import json
import logging
from typing import Any

from aiohttp import ClientError, ClientSession, ClientWebSocketResponse, WSMsgType

_LOGGER = logging.getLogger(__name__)


class KiiAudioClientError(Exception):
    """Base error for Kii Audio client failures."""


class KiiAudioClient:
    """Client for the Kii Audio plain WebSocket API."""

    def __init__(self, session: ClientSession, host: str) -> None:
        """Initialize the client."""
        self._session = session
        self.host = host
        self._ws: ClientWebSocketResponse | None = None
        self._listen_task: asyncio.Task[None] | None = None
        self._closed = False
        self._connected = asyncio.Event()
        self._listeners: list[Callable[[str, dict[str, Any]], None]] = []
        self._connection_listeners: list[Callable[[bool], None]] = []

    @property
    def _ws_url(self) -> str:
        return f"ws://{self.host}/ws"

    def add_listener(self, listener: Callable[[str, dict[str, Any]], None]) -> None:
        """Add a listener for pushed WebSocket events."""
        self._listeners.append(listener)

    def add_connection_listener(self, listener: Callable[[bool], None]) -> None:
        """Add a listener for WebSocket connection state changes."""
        self._connection_listeners.append(listener)

    async def start(self) -> None:
        """Start the WebSocket listener."""
        if self._listen_task is not None:
            return
        self._closed = False
        self._listen_task = asyncio.create_task(self._listen(), name="kii_audio_ws")

    async def stop(self) -> None:
        """Stop the WebSocket listener."""
        self._closed = True
        self._connected.clear()
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        if self._listen_task is not None:
            self._listen_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._listen_task
            self._listen_task = None

    async def send_event(self, event: str, data: dict[str, Any] | None = None) -> None:
        """Send an event to the device."""
        try:
            async with asyncio.timeout(3):
                await self._connected.wait()
        except TimeoutError as err:
            raise KiiAudioClientError("WebSocket is not connected") from err

        if self._ws is None or self._ws.closed:
            self._connected.clear()
            raise KiiAudioClientError("WebSocket is not connected")

        await self._ws.send_json({"event": event, "data": data or {}})

    async def set_zone_setting(self, zone_id: str, setting: str, value: Any) -> None:
        """Request a zone setting change."""
        await self.send_event(
            "setZoneSetting",
            {"zoneId": zone_id, "setting": setting, "value": value},
        )

    async def _listen(self) -> None:
        """Listen for WebSocket events and reconnect while active."""
        while not self._closed:
            try:
                async with asyncio.timeout(5):
                    ws = await self._session.ws_connect(self._ws_url, heartbeat=20)
                async with ws:
                    self._ws = ws
                    self._connected.set()
                    self._notify_connection_state(True)
                    await self.send_event("registerClient", {"token": "user_client"})
                    await self.send_event("getSystemInfo")
                    async for msg in ws:
                        if msg.type == WSMsgType.TEXT:
                            self._handle_message(msg.data)
                        elif msg.type in (WSMsgType.CLOSED, WSMsgType.ERROR):
                            break
            except (ClientError, TimeoutError, KiiAudioClientError) as err:
                if not self._closed:
                    _LOGGER.debug("Kii Audio WebSocket connection failed: %s", err)
            finally:
                was_connected = self._connected.is_set()
                self._connected.clear()
                self._ws = None
                if was_connected and not self._closed:
                    self._notify_connection_state(False)

            if not self._closed:
                await asyncio.sleep(5)

    def _handle_message(self, text: str) -> None:
        try:
            message = json.loads(text)
        except json.JSONDecodeError:
            _LOGGER.debug("Ignoring invalid Kii Audio WebSocket message: %s", text)
            return

        if not isinstance(message, dict):
            return

        event = message.pop("event", None)
        if not isinstance(event, str):
            return

        data = message.get("data")
        payload = data if isinstance(data, dict) else message
        payload = copy.deepcopy(payload)
        for listener in self._listeners:
            listener(event, payload)

    def _notify_connection_state(self, connected: bool) -> None:
        """Notify listeners that the WebSocket connection state changed."""
        for listener in self._connection_listeners:
            listener(connected)
