"""WebSocket client for receiving real-time device status from cloud."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

import aiohttp

from .const import LOGGER, WS_URL

RECONNECT_MIN_DELAY = 5
RECONNECT_MAX_DELAY = 300


class XthingsCloudWebSocket:
    """Xthings Cloud WebSocket client."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: str,
        on_device_status: Callable[[str, dict[str, Any]], None],
        on_token_expired: Callable[[], Any],
    ) -> None:
        self._session = session
        self._token = token
        self._on_device_status = on_device_status
        self._on_token_expired = on_token_expired
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
        self._reconnect_delay = RECONNECT_MIN_DELAY
        self._stopping = False

    @property
    def token(self) -> str:
        return self._token

    @token.setter
    def token(self, value: str) -> None:
        self._token = value

    async def async_start(self) -> None:
        """Start WebSocket connection."""
        self._stopping = False
        self._task = asyncio.create_task(self._async_run())

    async def async_stop(self) -> None:
        """Stop WebSocket connection."""
        self._stopping = True
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def _async_run(self) -> None:
        """Main loop with auto-reconnect."""
        while not self._stopping:
            try:
                await self._async_connect()
            except asyncio.CancelledError:
                break
            except Exception:  # noqa: BLE001
                LOGGER.exception("WebSocket unexpected error")
            if self._stopping:
                break
            LOGGER.info("WebSocket reconnecting in %s seconds", self._reconnect_delay)
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(self._reconnect_delay * 2, RECONNECT_MAX_DELAY)

    async def _async_connect(self) -> None:
        """Establish WebSocket connection and process messages."""
        LOGGER.info("WebSocket connecting to %s", WS_URL)
        try:
            self._ws = await self._session.ws_connect(WS_URL, heartbeat=30)
        except Exception as err:
            LOGGER.error("WebSocket connection failed: %s (%s)", err, type(err).__name__)
            return

        LOGGER.info("WebSocket connected")
        self._reconnect_delay = RECONNECT_MIN_DELAY

        # Send login auth
        await self._ws.send_json({"cmd": "login", "data": {"x-token": self._token}})
        LOGGER.info("WebSocket login sent")
        self._ping_task = asyncio.create_task(self._async_ping_loop())

        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    LOGGER.info("WebSocket raw message: %s", msg.data)
                    await self._async_handle_message(msg.json())
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    LOGGER.error("WebSocket error: %s", self._ws.exception())
                    break
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                    LOGGER.debug("WebSocket closed by server")
                    break
        except aiohttp.ClientError as err:
            LOGGER.error("WebSocket read error: %s", err)
        finally:
            self._stop_ping()
            if self._ws and not self._ws.closed:
                await self._ws.close()

    def _stop_ping(self) -> None:
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
        self._ping_task = None

    async def _async_ping_loop(self) -> None:
        """Send application-level ping every 55 seconds."""
        try:
            while self._ws and not self._ws.closed:
                await asyncio.sleep(55)
                if self._ws and not self._ws.closed:
                    await self._ws.send_json({"cmd": "ping"})
                    LOGGER.debug("WebSocket ping sent")
        except asyncio.CancelledError:
            pass
        except aiohttp.ClientError as err:
            LOGGER.error("WebSocket ping failed: %s", err)

    async def _async_handle_message(self, message: dict[str, Any]) -> None:
        """Handle incoming WebSocket message."""
        cmd = message.get("cmd")
        data = message.get("data", [])
        LOGGER.debug("WebSocket message received: cmd=%s", cmd)

        if cmd == "report.device.status":
            if isinstance(data, list):
                for device in data:
                    device_uuid = device.get("uuid")
                    status = device.get("status")
                    if device_uuid and status:
                        # Field conversion: power -> on
                        if "power" in status:
                            status["on"] = status["power"] == 1
                        # Field conversion: is_locked -> locked / jammed
                        if "is_locked" in status:
                            is_locked = status["is_locked"]
                            status["locked"] = is_locked == 2
                            status["jammed"] = is_locked == 3
                        # Field conversion: battery_percent -> battery
                        if "battery_percent" in status:
                            status["battery"] = status["battery_percent"]
                        self._on_device_status(device_uuid, status)
                    else:
                        LOGGER.warning("WebSocket device status missing uuid or status: %s", device)
            else:
                LOGGER.warning("WebSocket report.device.status data is not a list")

        elif cmd == "report.device.photo":
            if isinstance(data, list):
                for device in data:
                    device_uuid = device.get("uuid")
                    photo = device.get("status", {}).get("photo")
                    if device_uuid and photo:
                        self._on_device_status(device_uuid, {"snapshot_url": photo})
                    else:
                        LOGGER.warning("WebSocket device photo missing uuid or photo: %s", device)

        elif cmd == "report.device.connected":
            if isinstance(data, list):
                for device in data:
                    device_uuid = device.get("uuid")
                    online = device.get("status", {}).get("online")
                    if device_uuid and online is not None:
                        self._on_device_status(device_uuid, {"online": online})
                    else:
                        LOGGER.warning("WebSocket device connected missing uuid or online: %s", device)

        elif cmd == "auth_error":
            LOGGER.warning("WebSocket auth error, triggering token refresh")
            await self._on_token_expired()

        elif cmd == "pong":
            LOGGER.debug("WebSocket pong received")

        else:
            LOGGER.debug("WebSocket unknown cmd: %s", cmd)
