"""The Nettigo Air Monitor component."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectorError
import async_timeout
from nettigo_air_monitor import (
    ApiError,
    DictToObj,
    InvalidSensorData,
    NettigoAirMonitor,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_NAME, DEFAULT_UPDATE_INTERVAL, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["air_quality", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nettigo as config entry."""
    host = entry.data[CONF_HOST]

    websession = async_get_clientsession(hass)

    coordinator = NAMUpdateCoordinator(hass, websession, host, entry.unique_id)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class NAMUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Nettigo Air Monitor data."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
        host: str,
        unique_id: str | None,
    ) -> None:
        """Initialize."""
        self.host = host
        self.nam = NettigoAirMonitor(session, host)
        self._unique_id = unique_id

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_UPDATE_INTERVAL
        )

    async def _async_update_data(self) -> DictToObj:
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
    def unique_id(self) -> str | None:
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
