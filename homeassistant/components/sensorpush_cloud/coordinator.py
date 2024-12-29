"""Coordinator for the SensorPush Cloud integration."""

from __future__ import annotations

from collections.abc import Iterable

from sensorpush_ha import SensorPushCloudApi, SensorPushCloudData, SensorPushCloudHelper

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER, UPDATE_INTERVAL

type SensorPushCloudConfigEntry = ConfigEntry[SensorPushCloudCoordinator]


class SensorPushCloudCoordinator(DataUpdateCoordinator[dict[str, SensorPushCloudData]]):
    """SensorPush Cloud coordinator."""

    api: SensorPushCloudApi

    def __init__(self, hass: HomeAssistant, entry: SensorPushCloudConfigEntry) -> None:
        """Initialize the coordinator."""
        email, password = entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
        api = SensorPushCloudApi(hass, email, password)
        self.helper = SensorPushCloudHelper(api)
        super().__init__(
            hass, LOGGER, name=entry.title, update_interval=UPDATE_INTERVAL
        )

    async def _async_update_data(self) -> dict[str, SensorPushCloudData]:
        """Fetch data from API endpoints."""
        return await self.helper.async_get_data()

    async def async_get_device_ids(self) -> Iterable[str]:
        """Return the list of active device IDs."""
        return await self.helper.async_get_device_ids()
