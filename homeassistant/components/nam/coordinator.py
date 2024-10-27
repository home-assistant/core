"""The Nettigo Air Monitor coordinator."""

import logging

from nettigo_air_monitor import (
    ApiError,
    InvalidSensorDataError,
    NAMSensors,
    NettigoAirMonitor,
)
from tenacity import RetryError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


class NAMDataUpdateCoordinator(DataUpdateCoordinator[NAMSensors]):
    """Class to manage fetching Nettigo Air Monitor data."""

    def __init__(
        self,
        hass: HomeAssistant,
        nam: NettigoAirMonitor,
        unique_id: str,
    ) -> None:
        """Initialize."""
        self.unique_id = unique_id
        self.device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, unique_id)},
            name="Nettigo Air Monitor",
            sw_version=nam.software_version,
            manufacturer=MANUFACTURER,
            configuration_url=f"http://{nam.host}/",
        )
        self.nam = nam

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_UPDATE_INTERVAL
        )

    async def _async_update_data(self) -> NAMSensors:
        """Update data via library."""
        try:
            data = await self.nam.async_update()
        # We do not need to catch AuthFailed exception here because sensor data is
        # always available without authorization.
        except (ApiError, InvalidSensorDataError, RetryError) as error:
            raise UpdateFailed(error) from error

        return data
