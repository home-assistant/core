"""DataUpdateCoordinator for the Homeassistant Analytics integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from python_homeassistant_analytics import (
    CustomIntegration,
    HomeassistantAnalyticsClient,
    HomeassistantAnalyticsConnectionError,
    HomeassistantAnalyticsNotModifiedError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_TRACKED_CUSTOM_INTEGRATIONS,
    CONF_TRACKED_INTEGRATIONS,
    DOMAIN,
    LOGGER,
)


@dataclass(frozen=True)
class AnalyticsData:
    """Analytics data class."""

    core_integrations: dict[str, int]
    custom_integrations: dict[str, int]


class HomeassistantAnalyticsDataUpdateCoordinator(DataUpdateCoordinator[AnalyticsData]):
    """A Homeassistant Analytics Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, client: HomeassistantAnalyticsClient
    ) -> None:
        """Initialize the Homeassistant Analytics data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=12),
        )
        self._client = client
        self._tracked_integrations = self.config_entry.options[
            CONF_TRACKED_INTEGRATIONS
        ]
        self._tracked_custom_integrations = self.config_entry.options[
            CONF_TRACKED_CUSTOM_INTEGRATIONS
        ]

    async def _async_update_data(self) -> AnalyticsData:
        try:
            data = await self._client.get_current_analytics()
            custom_data = await self._client.get_custom_integrations()
        except HomeassistantAnalyticsConnectionError as err:
            raise UpdateFailed(
                "Error communicating with Homeassistant Analytics"
            ) from err
        except HomeassistantAnalyticsNotModifiedError:
            return self.data
        core_integrations = {
            integration: data.integrations.get(integration, 0)
            for integration in self._tracked_integrations
        }
        custom_integrations = {
            integration: get_custom_integration_value(custom_data, integration)
            for integration in self._tracked_custom_integrations
        }
        return AnalyticsData(core_integrations, custom_integrations)


def get_custom_integration_value(
    data: dict[str, CustomIntegration], domain: str
) -> int:
    """Get custom integration value."""
    if domain in data:
        return data[domain].total
    return 0
