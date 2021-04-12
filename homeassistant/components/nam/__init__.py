"""The Nettigo Air Monitor component."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectorError
import async_timeout
from nettigo_air_monitor import ApiError, InvalidSensorData, NettigoAirMonitor

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_NAME, DEFAULT_UPDATE_INTERVAL, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["air_quality", "sensor"]


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up Nettigo as config entry."""
    host = entry.data[CONF_HOST]

    websession = async_get_clientsession(hass)

    coordinator = NAMUpdateCoordinator(hass, websession, host, entry.unique_id)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class NAMUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Nettigo Air Monitor data."""

    def __init__(
        self, hass: HomeAssistantType, session: ClientSession, host: str, unique_id: str
    ):
        """Initialize."""
        self.host = host
        self.nam = NettigoAirMonitor(session, host)
        self._unique_id = unique_id

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_UPDATE_INTERVAL
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # Device firmware uses synchronous code and doesn't respond to http queries
            # when reading data from sensors. The nettigo-air-quality library tries to
            # get the data 4 times, so we use a longer than usual timeout here.
            with async_timeout.timeout(30):
                data = await self.nam.async_update()
        except (ApiError, ClientConnectorError, InvalidSensorData) as error:
            raise UpdateFailed(error) from error

        _LOGGER.debug(data)

        return data

    @property
    def unique_id(self) -> str:
        """Return a unique_id."""
        return self._unique_id

    @property
    def device_info(self) -> dict[str, Any]:
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "connections": {(CONNECTION_NETWORK_MAC, self._unique_id)},
            "name": DEFAULT_NAME,
            "sw_version": self.nam.software_version,
            "manufacturer": MANUFACTURER,
        }
