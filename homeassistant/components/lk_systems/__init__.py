"""LK Systems integration for Home Assistant.

This module handles the setup and core functionality of the LK Systems integration.
"""

import logging
import time

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import LKSystemDataUpdateCoordinator
from .exceptions import InvalidAuth

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    api = LKWebServerAPI(entry.data["email"], entry.data["password"])
    await api.login()

    coordinator = LKSystemDataUpdateCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN] = {
        "coordinator": coordinator,
        "api": api,
    }

    await hass.config_entries.async_forward_entry_setup(entry, "climate")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data.pop(DOMAIN, None)
    if data:
        await data["api"].close()
        await hass.config_entries.async_unload_platforms(entry, ["climate"])
    return True


class LKWebServerAPI:
    """An API client for the LK Systems webserver."""

    def __init__(self, email, password) -> None:
        """Initialize the API client."""
        self.base_url = "https://my.lk.nu"
        self.email = email
        self.password = password
        self.session = None

    async def login(self):
        """Log in to the LK Systems API and initialize the session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()

        login_url = f"{self.base_url}/login"
        payload = {"email": self.email, "password": self.password}
        async with self.session.post(login_url, data=payload) as response:
            response.raise_for_status()
            result = await response.json()
            if result.get("error") == "1":
                _LOGGER.error("Login failed: %s", result.get("msg", "Unknown error"))
                raise InvalidAuth(result.get("msg", "Access denied."))

    async def get_main_data(self):
        """Fetch the main data from the LK Systems webserver."""
        url = f"{self.base_url}/main.json"
        if self.session is None:
            return {}
        async with self.session.get(url) as response:
            response.raise_for_status()
            return await response.json()

    async def set_room_temperature(self, zone_id, temperature) -> dict:
        """Set the target temperature for a specific zone.

        :param zone_id: The ID of the zone (tid parameter).
        :param temperature: The target temperature in °C (float).
        """
        url = f"{self.base_url}/update.cgi"

        params = {
            "tid": zone_id,
            "set_room_deg": int(
                temperature * 100
            ),  # Convert temperature to integer format expected by API
            "_": int(time.time() * 1000),  # Adds a timestamp to avoid caching
        }

        if self.session is None:
            return {}

        async with self.session.get(url, params=params) as response:
            response.raise_for_status()
            try:
                result = await response.json()
            except aiohttp.ContentTypeError as e:
                _LOGGER.error("Failed to parse JSON response: %s", e)
                result = None
            _LOGGER.info("Set temperature response for zone %s: %s", zone_id, result)
            return result

    def get_zone_names(self, data) -> list[str]:
        """Decode zone names from raw data."""
        raw_names = data.get("name", [])
        decoded_names = []
        for index, name in enumerate(raw_names):
            try:
                # Attempt decoding with UTF-8
                decoded_name = bytes.fromhex(name).decode("utf-8")
            except UnicodeDecodeError:
                try:
                    # Fallback to ISO-8859-1 if UTF-8 decoding fails
                    decoded_name = bytes.fromhex(name).decode("iso-8859-1")
                except UnicodeDecodeError as e:
                    _LOGGER.error(
                        "Error decoding name at index %d ('%s'): %s. Using fallback",
                        index,
                        name,
                        e,
                    )
                    decoded_name = f"Zone {index + 1}"  # Fallback name
            decoded_names.append(decoded_name)
        return decoded_names

    async def close(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
