"""WebSocket client for Rexense devices."""

import asyncio
import logging
from typing import Any

from aiohttp import (
    ClientError,
    ClientSession,
    ClientWebSocketResponse,
    ClientWSTimeout,
    WSMsgType,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import DOMAIN, REXSENSE_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


class RexenseWebsocketClient:
    """Manages WebSocket connection to a Rexense device."""

    hass: HomeAssistant
    ws: ClientWebSocketResponse | None
    connected: bool
    _running: bool
    _task: asyncio.Task[None] | None

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        model: str,
        url: str,
        sw_build_id: str,
        feature_map: list[dict[str, str]],
    ) -> None:
        """Initialize the WebSocket client."""
        self.hass = hass
        self.device_id = device_id
        self.model = model
        self.sw_build_id = sw_build_id
        self.feature_map = feature_map
        self.url = url
        self.ws: ClientWebSocketResponse | None = None
        self.connected = False
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self.last_values: dict[str, float] = {}
        self.switch_state: bool | None = None
        self.ping_interval = 30

        self.signal_update = f"{DOMAIN}_{device_id}_update"

    async def connect(self) -> None:
        """Connect to the device and start listening."""
        if self._running:
            return
        session = aiohttp_client.async_get_clientsession(self.hass)
        _LOGGER.debug("Attempting WebSocket connection to %s", self.url)
        try:
            ws = await session.ws_connect(
                self.url,
                timeout=ClientWSTimeout(ws_close=10),
                heartbeat=self.ping_interval,
                autoping=True,
            )
        except Exception as err:
            _LOGGER.error(
                "Initial WebSocket connect failed for %s: %s", self.device_id, err
            )
            self._running = False
            raise
        else:
            self._running = True
            self.ws = ws
            self.connected = True
            _LOGGER.info("WebSocket connected to device %s", self.device_id)
            # Kick off the reconnect-and-listen loop
            self._task = self.hass.loop.create_task(self._run_loop(session))

    async def async_set_switch(self, on: bool) -> None:
        """Send ON/OFF command to device via WebSocket."""
        if not self.connected or self.ws is None:
            raise RuntimeError("WebSocket is not connected.")
        # payload {"FunctionCode":"InvokeCmd","Payload":{"Onoff":{"status":on}}}
        control = "On" if on else "Off"
        payload = {
            "FunctionCode": "InvokeCmd",
            "Payload": {control: {}},
        }
        try:
            await self.ws.send_json(payload)
        except Exception as err:
            _LOGGER.error("Failed to send switch command: %s", err)
            raise

    async def _run_loop(self, session: ClientSession) -> None:
        """Run the WebSocket listen and auto-reconnect loop."""
        first_try = True
        while self._running:
            try:
                if not first_try:
                    _LOGGER.info("Reconnecting to device %s", self.device_id)
                    self.ws = await session.ws_connect(
                        self.url,
                        timeout=ClientWSTimeout(ws_close=10),
                        heartbeat=self.ping_interval,
                        autoping=True,
                    )
                    self.connected = True
                    _LOGGER.info("WebSocket reconnected to device %s", self.device_id)
                else:
                    first_try = False

                # Mypy needs to know ws is not None
                assert self.ws is not None
                async for msg in self.ws:
                    if msg.type == WSMsgType.TEXT:
                        data = None
                        try:
                            data = msg.json()
                        except ValueError as e:
                            _LOGGER.error("Received invalid JSON: %s, data: %s", e, msg)
                            continue
                        _LOGGER.debug("Received message: %s", data)
                        self._handle_message(data)
                    elif msg.type == WSMsgType.ERROR:
                        # ws.exception() only valid if ws is not None
                        assert self.ws is not None
                        _LOGGER.error(
                            "WebSocket error for %s: %s",
                            self.device_id,
                            self.ws.exception(),
                        )
                        break
                    elif msg.type in (WSMsgType.CLOSED, WSMsgType.CLOSING):
                        _LOGGER.warning(
                            "WebSocket connection closed for %s", self.device_id
                        )
                        break
            except (TimeoutError, ClientError) as err:
                if self._running:
                    _LOGGER.error(
                        "WebSocket connection failed for %s: %s", self.device_id, err
                    )
            # skip loop
            self.connected = False
            if self.ws is not None:
                try:
                    await self.ws.close()
                except (ClientError, RuntimeError) as err:
                    _LOGGER.debug("Error closing websocket: %s", err)
                finally:
                    self.ws = None

            if self._running:
                await asyncio.sleep(5)
                continue

    def _handle_message(self, data: dict[str, Any]) -> None:
        """Process incoming message from WebSocket."""

        func = data.get("FunctionCode") or data.get("function") or data.get("func")

        if func and isinstance(func, str):
            func = func.lower()

        if func == "notifystatus":
            payload = data.get("Payload") or {}
            _LOGGER.debug("Received payload: %s", payload)
            if not payload:
                _LOGGER.debug("No payload in message")
            else:
                for k, v in payload.items():
                    key = k.replace("_1", "")
                    if key == "PowerSwitch":
                        self.switch_state = v not in ("0", False)
                        _LOGGER.debug("Update switch state: %s", self.switch_state)
                    elif key in REXSENSE_SENSOR_TYPES:
                        _LOGGER.debug("Update sensor %s: %s", key, v)
                        self.last_values[key] = v

                dispatcher_send(self.hass, self.signal_update)
        else:
            _LOGGER.debug("Unhandled function %s: %s", func, data)

    async def disconnect(self) -> None:
        """Disconnect and stop the WebSocket client."""
        _LOGGER.info("Disconnecting WebSocket for device %s", self.device_id)
        self._running = False
        if self.ws is not None:
            await self.ws.close()
        if self._task:
            await self._task
        self.ws = None
        self.connected = False
