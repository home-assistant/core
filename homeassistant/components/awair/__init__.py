"""The awair component."""
from __future__ import annotations

from asyncio import gather
from typing import Any

from async_timeout import timeout
from python_awair import Awair
from python_awair.exceptions import AuthError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_TIMEOUT, DOMAIN, LOGGER, UPDATE_INTERVAL, AwairResult

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Awair integration from a config entry."""
    session = async_get_clientsession(hass)
    coordinator = AwairDataUpdateCoordinator(hass, config_entry, session)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Awair configuration."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class AwairDataUpdateCoordinator(DataUpdateCoordinator):
    """Define a wrapper class to update Awair data."""

    def __init__(self, hass, config_entry, session) -> None:
        """Set up the AwairDataUpdateCoordinator class."""
        access_token = config_entry.data[CONF_ACCESS_TOKEN]
        self._awair = Awair(access_token=access_token, session=session)
        self._config_entry = config_entry

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

    async def _async_update_data(self) -> Any | None:
        """Update data via Awair client library."""
        async with timeout(API_TIMEOUT):
            try:
                LOGGER.debug("Fetching users and devices")
                user = await self._awair.user()
                devices = await user.devices()
                results = await gather(
                    *(self._fetch_air_data(device) for device in devices)
                )
                return {result.device.uuid: result for result in results}
            except AuthError as err:
                raise ConfigEntryAuthFailed from err
            except Exception as err:
                raise UpdateFailed(err) from err

    async def _fetch_air_data(self, device):
        """Fetch latest air quality data."""
        LOGGER.debug("Fetching data for %s", device.uuid)
        air_data = await device.air_data_latest()
        LOGGER.debug(air_data)
        return AwairResult(device=device, air_data=air_data)
