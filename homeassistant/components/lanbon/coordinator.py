"""LANBON API client + DataUpdateCoordinator."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class LanbonApi:
    def __init__(self, hass: HomeAssistant, host: str, port: int, token: str) -> None:
        self.hass = hass
        self.host = host
        self.port = port or DEFAULT_PORT
        self.token = token
        self._session = async_get_clientsession(hass)
        self._ws_task: asyncio.Task | None = None
        self._listeners: list = []

    @property
    def base(self) -> str:
        return f"http://{self.host}:{self.port}"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def async_get_info(self) -> dict[str, Any]:
        async with self._session.get(
            f"{self.base}/api/v1/info", headers=self._headers(), timeout=8
        ) as resp:
            if resp.status == 401:
                raise PermissionError("invalid token")
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def async_get_devices(self) -> dict[str, Any]:
        async with self._session.get(
            f"{self.base}/api/v1/devices", headers=self._headers(), timeout=8
        ) as resp:
            if resp.status == 401:
                raise PermissionError("invalid token")
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def async_command(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._session.post(
            f"{self.base}/api/v1/command",
            headers={**self._headers(), "Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=8,
        ) as resp:
            if resp.status == 401:
                raise PermissionError("invalid token")
            resp.raise_for_status()
            return await resp.json(content_type=None)

    def add_listener(self, cb) -> None:
        self._listeners.append(cb)

    async def async_start_ws(self, on_message) -> None:
        self.add_listener(on_message)
        if self._ws_task and not self._ws_task.done():
            return
        self._ws_task = self.hass.async_create_task(self._ws_loop())

    async def async_stop_ws(self) -> None:
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None

    async def _ws_loop(self) -> None:
        url = f"ws://{self.host}:{self.port}/api/v1/ws?token={self.token}"
        while True:
            try:
                async with self._session.ws_connect(url, heartbeat=30) as ws:
                    _LOGGER.debug("LANBON WS connected %s", url)
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                            except json.JSONDecodeError:
                                continue
                            for cb in list(self._listeners):
                                cb(data)
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("LANBON WS error: %s", err)
            await asyncio.sleep(5)


class LanbonCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, api: LanbonApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # push via WS; poll as fallback below
        )
        self.api = api
        from datetime import timedelta

        self.update_interval = timedelta(seconds=30)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.async_get_devices()
        except PermissionError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(str(err)) from err

    def handle_ws(self, data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            return
        if data.get("type") == "state" or "devices" in data:
            # Ensure coordinator update runs on HA event loop
            self.hass.loop.call_soon_threadsafe(self.async_set_updated_data, data)
