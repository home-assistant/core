"""A demonstration 'hub' that connects several devices."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging

import httpx

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class Hub:
    """Hub for TRIGGERcmd."""

    manufacturer = "TRIGGERcmd"

    def __init__(self, hass: HomeAssistant, token: str) -> None:
        """Init hub."""
        self._token = token
        self._hass = hass
        self._name = "TRIGGERcmd"
        self._id = token

        url = "https://www.triggercmd.com/api/command/simplelist"
        headers = {"Authorization": "Bearer " + token}
        r = httpx.get(url, headers=headers)
        self.switches = []
        for item in r.json():
            trigger = item["trigger"]
            computer = item["computer"]
            self.switches.append(
                Switch(f"{computer}.{trigger}", f"{computer} | {trigger}", self)
            )

        self.online = True

    @property
    def hub_id(self) -> str:
        """ID for hub."""
        return self._id

    async def test_connection(self) -> bool:
        """Test connectivity to the hub is OK."""
        await asyncio.sleep(1)
        return True


class Switch:
    """switch (device for HA) for TRIGGERcmd."""

    def __init__(self, switchid: str, name: str, hub: Hub) -> None:
        """Init switch."""
        self._id = switchid
        self.hub = hub
        self.name = name
        self._is_on = False
        self._callbacks: set[Callable[[], None]] = set()
        self._loop = asyncio.get_event_loop()
        # Some static information about this device
        self.firmware_version = "1.0.0"
        self.model = "Trigger Device"

    @property
    def switch_id(self) -> str:
        """Return ID for switch."""
        return self._id

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register callback, called when switch changes state."""
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)

    @property
    def online(self) -> float:
        """Switch is online."""
        return True

    @property
    def is_on(self) -> bool:
        """Switch is on."""
        return True
