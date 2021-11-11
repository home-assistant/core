"""The awair component."""
from __future__ import annotations

from asyncio import gather
from typing import Any

from async_timeout import timeout
from python_awair import Awair
from python_awair.exceptions import AuthError

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from .const import (
    API_TIMEOUT,
    DATA_UPDATE_INTERVAL,
    DEVICE_UPDATE_INTERVAL,
    DOMAIN,
    LOGGER,
    AwairResult,
)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass, config_entry) -> bool:
    """Set up Awair integration from a config entry."""
    session = async_get_clientsession(hass)
    coordinator = AwairDataUpdateCoordinator(hass, config_entry, session)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass, config_entry) -> bool:
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
        self._awair_devices = []
        self._last_device_update = None
        self._config_entry = config_entry

        super().__init__(
            hass, LOGGER, name=DOMAIN, update_interval=DATA_UPDATE_INTERVAL
        )

    async def _async_update_data(self) -> Any | None:
        """Update data via Awair client library."""
        async with timeout(API_TIMEOUT):
            try:
                devices = await self._fetch_devices()
                results = await gather(
                    *(self._fetch_air_data(device) for device in devices)
                )
                return {result.device.uuid: result for result in results}
            except AuthError as err:
                self._last_device_update = None
                raise ConfigEntryAuthFailed from err
            except Exception as err:
                self._last_device_update = None
                raise UpdateFailed(err) from err

    async def _fetch_devices(self):
        """Fetch user's device list, less frequently than device data."""
        now = utcnow()

        if (
            self._last_device_update is None
            or now > self._last_device_update + DEVICE_UPDATE_INTERVAL
        ):
            LOGGER.debug("Fetching users and devices")
            user = await self._awair.user()
            self._awair_devices = await user.devices()
            self._last_device_update = now

        return self._awair_devices

    async def _fetch_air_data(self, device):
        """Fetch latest air quality data."""
        # pylint: disable=no-self-use
        LOGGER.debug("Fetching data for %s", device.uuid)
        air_data = await device.air_data_latest()
        LOGGER.debug(air_data)
        return AwairResult(device=device, air_data=air_data)
