"""Coordinator for the SensorPush Cloud integration."""

from __future__ import annotations

from sensorpush_ha import (
    SensorPushCloudApi,
    SensorPushCloudData,
    SensorPushCloudError,
    SensorPushCloudHelper,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER, UPDATE_INTERVAL

type SensorPushCloudConfigEntry = ConfigEntry[SensorPushCloudCoordinator]


class SensorPushCloudCoordinator(DataUpdateCoordinator[dict[str, SensorPushCloudData]]):
    """SensorPush Cloud coordinator."""

    def __init__(self, hass: HomeAssistant, entry: SensorPushCloudConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=entry.title,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        email, password = entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
        clientsession = async_get_clientsession(hass)
        api = SensorPushCloudApi(email, password, clientsession)
        self.helper = SensorPushCloudHelper(api)

    async def _async_update_data(self) -> dict[str, SensorPushCloudData]:
        """Fetch data from API endpoints."""
        try:
            return await self.helper.async_get_data()
        except SensorPushCloudError as e:
            raise UpdateFailed(e) from e
