"""Lepro API client."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow


class LoproApiClient:
    """Handle all Lepro API calls, using an OAuth2 session for auth."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        api_host: str,
    ) -> None:
        """Initialize the API client."""
        self._hass = hass
        self._session = oauth_session
        self._api_host = api_host

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Fetch the device list."""
        timestamp = int(time.time())
        resp = await self._session.async_request(
            "GET",
            f"{self._api_host}/devicestate/list/timestamp/{timestamp}",
        )
        resp.raise_for_status()
        body = await resp.json()
        return body["data"]["list"]

    async def async_get_device_state(self, did: int) -> dict[str, Any]:
        """Fetch state for a single device."""
        timestamp = int(time.time())
        resp = await self._session.async_request(
            "GET",
            f"{self._api_host}/devicestate/did/{did}/timestamp/{timestamp}",
        )
        resp.raise_for_status()
        body = await resp.json()
        return body["data"]

    async def async_turn_on(self, did: int) -> None:
        """Turn on a device."""
        await self._control(did, 1)

    async def async_turn_off(self, did: int) -> None:
        """Turn off a device."""
        await self._control(did, 2)

    async def async_set_color(self, did: int, rgb: tuple[int, int, int]) -> None:
        """Set device color. rgb is a (r, g, b) tuple with values 0-255."""
        color_hex = "#{:02x}{:02x}{:02x}".format(*rgb)
        await self._setcommand(did, 3, color_hex)

    async def async_set_color_temp(self, did: int, kelvin: int) -> None:
        """Set device color temperature in Kelvin."""
        await self._setcommand(did, 4, f"{kelvin}K")

    async def async_set_brightness(self, did: int, brightness_pct: int) -> None:
        """Set device brightness. brightness_pct is 0-100."""
        await self._setcommand(did, 5, brightness_pct)

    async def _control(self, did: int, cmd_type: int) -> None:
        """Send a basic on/off command to a device."""
        val = 1 if cmd_type == 1 else 0
        await self._setcommand(did, cmd_type, val)

    async def _setcommand(self, did: int, cmd_type: int, val: int | str) -> None:
        """Send a setcommand request to a device."""
        resp = await self._session.async_request(
            "GET",
            f"{self._api_host}/device/setcommand",
            params={"did": did, "type": cmd_type, "val": val},
        )
        resp.raise_for_status()
