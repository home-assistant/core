"""Coordinator for the World Air Quality Index (WAQI) integration."""
from __future__ import annotations

from datetime import timedelta

from aiowaqi import WAQIAirQuality, WAQIClient, WAQIError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_STATION_NUMBER, DOMAIN, LOGGER


class WAQIDataUpdateCoordinator(DataUpdateCoordinator[WAQIAirQuality]):
    """The WAQI Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, client: WAQIClient) -> None:
        """Initialize the WAQI data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )
        self._client = client

    async def _async_update_data(self) -> WAQIAirQuality:
        try:
            return await self._client.get_by_station_number(
                self.config_entry.data[CONF_STATION_NUMBER]
            )
        except WAQIError as exc:
            raise UpdateFailed from exc
