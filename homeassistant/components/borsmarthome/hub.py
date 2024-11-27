"""A demonstration 'hub' that connects several devices."""

from __future__ import annotations

# In a real implementation, this would be in an external library that's on PyPI.
# The PyPI package needs to be included in the `requirements` section of manifest.json
# See https://developers.home-assistant.io/docs/creating_integration_manifest
# for more information.
# This dummy hub always returns 3 rollers.

import requests

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import Callable

from aiohttp import ClientSession, ClientResponse

import asyncio
import aiohttp


class AveHub:
    """AVE WebServer hub."""

    def __init__(self, hass: HomeAssistant, host: str, apiKey: str) -> None:
        """Init AVE hub."""
        self._host = host
        self._apiKey = apiKey
        self._hass = hass
        self._name = "AVE WebServer"
        self._id = f"avebus_{host.lower()}"
        self._devices: list[RollerShutter] = []

        self._headers = {"x-api-key": self._apiKey}

    async def async_load_entities(self):
        session = aiohttp.ClientSession()
        async with session.get(
            f"{self._host}/avebus/rollershutters", headers=self._headers
        ) as r:
            data = await r.json()
        await session.close()

        self.devices.extend(
            [
                RollerShutter(self, item["Name"], item["Channel"], item["Percentage"])
                for item in data
            ]
        )

    @property
    def hub_id(self) -> str:
        """ID for hub."""
        return self._id

    @property
    def devices(self) -> list[RollerShutter]:
        """List."""
        return self._devices

    @property
    def host(self) -> str:
        """Host for hub."""
        return self._host

    @property
    def headers(self):
        """Api key for hub."""
        return self._headers


class RollerShutter:
    """AVE roller shutter."""

    def __init__(self, hub: AveHub, name, channel, percentage) -> None:
        """Init ave roller shutter."""
        self._name = name
        self._channel = channel
        self._hub = hub
        self._callbacks = set()
        self._position = percentage

    @property
    def name(self) -> str:
        """Return name for roller."""
        return self._name

    @property
    def channel(self) -> str:
        """Return ID for roller."""
        return self._channel

    @property
    def position(self) -> float:
        """Return position for roller."""
        return self._position

    async def async_request_position(self, position) -> None:
        """Set posiiton."""
        session = aiohttp.ClientSession()
        await session.post(
            f"{self._hub.host}/avebus/{self._channel}?percentage={position}",
            headers=self._hub.headers,
        )
        await session.close()

    async def async_stop(self) -> None:
        """Stop roller."""
        session = aiohttp.ClientSession()
        async with session.post(
            f"{self._hub.host}/avebus/{self._channel}?command=stop",
            headers=self._hub.headers,
        ) as r:
            data = await r.json()
        await session.close()

        entities = [
            {
                "percent": item["previousPerc"],
            }
            for item in data
        ]
        self._position = entities[0]["percent"]

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    # In a real implementation, this library would call it's call backs when it was
    # notified of any state changeds for the relevant device.
    async def async_publish_updates(self) -> None:
        """Schedule call all registered callbacks."""
        for callback in self._callbacks:
            callback()
