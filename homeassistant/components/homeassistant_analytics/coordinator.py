"""DataUpdateCoordinator for the Homeassistant Analytics integration."""
from __future__ import annotations

from datetime import timedelta

from python_homeassistant_analytics import (
    HomeassistantAnalyticsClient,
    HomeassistantAnalyticsConnectionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_TRACKED_INTEGRATIONS, DOMAIN, LOGGER


class HomeassistantAnalyticsDataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, int]]
):
    """A Homeassistant Analytics Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Homeassistant Analytics data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=12),
        )
        self._client = HomeassistantAnalyticsClient(
            session=async_get_clientsession(hass)
        )
        self._tracked_integrations = self.config_entry.options[
            CONF_TRACKED_INTEGRATIONS
        ]

    async def _async_update_data(self) -> dict[str, int]:
        try:
            data = await self._client.get_analytics()
        except HomeassistantAnalyticsConnectionError as err:
            raise UpdateFailed(
                "Error communicating with Homeassistant Analytics"
            ) from err
        return {
            integration: data.current.integrations[integration]
            for integration in self._tracked_integrations
        }
