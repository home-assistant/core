"""DataUpdateCoordinators for awair integration."""

from __future__ import annotations

from asyncio import gather, timeout
from dataclasses import dataclass
from datetime import timedelta

from aiohttp import ClientSession
from python_awair import Awair, AwairLocal
from python_awair.air_data import AirData
from python_awair.devices import AwairBaseDevice, AwairLocalDevice
from python_awair.exceptions import AuthError, AwairError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
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

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        update_interval: timedelta | None,
    ) -> None:
        """Set up the AwairDataUpdateCoordinator class."""
        self._config_entry = config_entry
        self.title = config_entry.title

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _fetch_air_data(self, device: AwairBaseDevice) -> AwairResult:
        """Fetch latest air quality data."""
        LOGGER.debug("Fetching data for %s", device.uuid)
        air_data = await device.air_data_latest()
        LOGGER.debug(air_data)
        return AwairResult(device=device, air_data=air_data)


class AwairCloudDataUpdateCoordinator(AwairDataUpdateCoordinator):
    """Define a wrapper class to update Awair data from Cloud API."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, session: ClientSession
    ) -> None:
        """Set up the AwairCloudDataUpdateCoordinator class."""
        access_token = config_entry.data[CONF_ACCESS_TOKEN]
        self._awair = Awair(access_token=access_token, session=session)

        super().__init__(hass, config_entry, UPDATE_INTERVAL_CLOUD)

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

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, session: ClientSession
    ) -> None:
        """Set up the AwairLocalDataUpdateCoordinator class."""
        self._awair = AwairLocal(
            session=session, device_addrs=[config_entry.data[CONF_HOST]]
        )

        super().__init__(hass, config_entry, UPDATE_INTERVAL_LOCAL)

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
