"""DataUpdateCoordinators for awair integration."""

from __future__ import annotations

from asyncio import gather, timeout
from dataclasses import dataclass
from datetime import timedelta

from python_awair import Awair, AwairLocal
from python_awair.air_data import AirData
from python_awair.devices import AwairBaseDevice, AwairLocalDevice
from python_awair.exceptions import AuthError, AwairError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    API_TIMEOUT,
    DOMAIN,
    LOGGER,
    UPDATE_INTERVAL_CLOUD,
    UPDATE_INTERVAL_LOCAL,
)


@dataclass
class AwairResult:
    """Wrapper class to hold an awair device and set of air data."""

    device: AwairBaseDevice
    air_data: AirData


class AwairDataUpdateCoordinator(DataUpdateCoordinator[dict[str, AwairResult]]):
    """Define a wrapper class to update Awair data."""

    _update_interval: timedelta
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up the AwairDataUpdateCoordinator class."""
        super().__init__(
            hass, LOGGER, name=DOMAIN, update_interval=self._update_interval
        )

    async def _fetch_air_data(self, device: AwairBaseDevice) -> AwairResult:
        """Fetch latest air quality data."""
        LOGGER.debug("Fetching data for %s", device.uuid)
        air_data = await device.air_data_latest()
        LOGGER.debug(air_data)
        return AwairResult(device=device, air_data=air_data)


class AwairCloudDataUpdateCoordinator(AwairDataUpdateCoordinator):
    """Define a wrapper class to update Awair data from Cloud API."""

    _update_interval = UPDATE_INTERVAL_CLOUD

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up the AwairCloudDataUpdateCoordinator class."""
        super().__init__(hass)
        self._awair = Awair(
            access_token=self.config_entry.data[CONF_ACCESS_TOKEN],
            session=async_get_clientsession(hass),
        )

    async def _async_update_data(self) -> dict[str, AwairResult]:
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


class AwairLocalDataUpdateCoordinator(AwairDataUpdateCoordinator):
    """Define a wrapper class to update Awair data from the local API."""

    _device: AwairLocalDevice | None = None
    _update_interval = UPDATE_INTERVAL_LOCAL

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up the AwairLocalDataUpdateCoordinator class."""
        super().__init__(hass)
        self._awair = AwairLocal(
            session=async_get_clientsession(hass),
            device_addrs=[self.config_entry.data[CONF_HOST]],
        )

    async def _async_update_data(self) -> dict[str, AwairResult]:
        """Update data via Awair client library."""
        async with timeout(API_TIMEOUT):
            try:
                if self._device is None:
                    LOGGER.debug("Fetching devices")
                    devices = await self._awair.devices()
                    self._device = devices[0]
                result = await self._fetch_air_data(self._device)
            except AwairError as err:
                LOGGER.error("Unexpected API error: %s", err)
                raise UpdateFailed(err) from err
            return {result.device.uuid: result}
