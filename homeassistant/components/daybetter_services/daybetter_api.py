"""DayBetter API client."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)


class DayBetterApi:
    """DayBetter API client."""

    def __init__(self, hass: HomeAssistant, token: str) -> None:
        """Initialize the API client."""
        self.hass = hass
        self.token = token
        self._auth_valid = True

    async def fetch_devices(self) -> list[dict[str, Any]]:
        """Get list of devices."""
        try:
            session = async_get_clientsession(self.hass)
            url = API_BASE_URL + "hass/devices"
            headers = {"Authorization": f"Bearer {self.token}"}
            async with session.post(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    devices = data.get("data", [])
                    _LOGGER.debug("Fetched devices: %s", devices)
                    self._auth_valid = True
                    return devices
                if resp.status == 401:
                    _LOGGER.error("Authentication failed - token may be expired")
                    self._auth_valid = False
                    return []
                _LOGGER.error("Failed to fetch devices: %s", await resp.text())
                return []
        except Exception as e:
            _LOGGER.exception("Exception while fetching devices: %s", e)
            return []

    async def fetch_pids(self) -> dict[str, Any]:
        """Get list of PIDs for different device types."""
        try:
            session = async_get_clientsession(self.hass)
            url = API_BASE_URL + "hass/pids"
            headers = {"Authorization": f"Bearer {self.token}"}
            async with session.post(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._auth_valid = True
                    return data.get("data", {})
                if resp.status == 401:
                    _LOGGER.error("Authentication failed - token may be expired")
                    self._auth_valid = False
                    return {}
                _LOGGER.error("Failed to fetch PIDs: %s", await resp.text())
                return {}
        except Exception as e:
            _LOGGER.exception("Exception while fetching PIDs: %s", e)
            return {}

    async def control_device(
        self,
        device_name: str,
        action: bool,
        brightness: int | None,
        hs_color: tuple[float, float] | None,
        color_temp: int | None,
    ) -> dict[str, Any]:
        """Control a device."""
        session = async_get_clientsession(self.hass)
        url = API_BASE_URL + "hass/control"
        headers = {"Authorization": f"Bearer {self.token}"}

        # Priority: color temperature > color > brightness > switch
        if color_temp is not None:
            # Convert mireds to Kelvin
            kelvin = int(1000000 / color_temp)
            payload = {
                "deviceName": device_name,
                "type": 4,  # Type 4 is color temperature control
                "kelvin": kelvin,
            }
        elif hs_color is not None:
            h, s = hs_color
            v = (brightness / 255) if brightness is not None else 1.0
            payload = {
                "deviceName": device_name,
                "type": 3,
                "hue": h,
                "saturation": s / 100,
                "brightness": v,
            }
        elif brightness is not None:
            payload = {"deviceName": device_name, "type": 2, "brightness": brightness}
        else:
            # Type 1 control switch is used by default
            payload = {"deviceName": device_name, "type": 1, "on": action}

        try:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    self._auth_valid = True
                    return await resp.json()
                if resp.status == 401:
                    _LOGGER.error("Authentication failed - token may be expired")
                    self._auth_valid = False
                    return {"code": 0, "message": "Authentication failed"}
                _LOGGER.error(
                    "Failed to control device %s: HTTP %d", device_name, resp.status
                )
                return {"code": 0, "message": f"HTTP {resp.status}"}
        except Exception as e:
            _LOGGER.exception(
                "Exception while controlling device %s: %s", device_name, e
            )
            return {"code": 0, "message": str(e)}

    async def fetch_mqtt_config(self) -> dict[str, Any]:
        """Get MQTT connection configuration information."""
        session = async_get_clientsession(self.hass)
        url = API_BASE_URL + "hass/cert"
        headers = {"Authorization": f"Bearer {self.token}"}
        _LOGGER.debug("Requesting MQTT configuration URL: %s", url)

        try:
            async with session.post(url, headers=headers) as resp:
                _LOGGER.debug("MQTT configuration API response status: %d", resp.status)

                if resp.status == 200:
                    data = await resp.json()
                    _LOGGER.debug("MQTT configuration API raw response: %s", data)
                    self._auth_valid = True
                    return data.get("data", {})
                if resp.status == 401:
                    _LOGGER.error("Authentication failed - token may be expired")
                    self._auth_valid = False
                    return {}
                error_text = await resp.text()
                _LOGGER.error("Failed to fetch MQTT config: %s", error_text)
                return {}
        except Exception as e:
            _LOGGER.exception("Exception while fetching MQTT config: %s", e)
            return {}

    @property
    def is_authenticated(self) -> bool:
        """Check if the API client is authenticated."""
        return self._auth_valid
