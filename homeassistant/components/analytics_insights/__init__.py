"""The Homeassistant Analytics integration."""

from __future__ import annotations

from dataclasses import dataclass

from python_homeassistant_analytics import (
    HomeassistantAnalyticsClient,
    HomeassistantAnalyticsConnectionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_TRACKED_INTEGRATIONS
from .coordinator import HomeassistantAnalyticsDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
AnalyticsInsightsConfigEntry = ConfigEntry["AnalyticsInsightsData"]


@dataclass(frozen=True)
class AnalyticsInsightsData:
    """Analytics data class."""

    coordinator: HomeassistantAnalyticsDataUpdateCoordinator
    names: dict[str, str]


async def async_setup_entry(
    hass: HomeAssistant, entry: AnalyticsInsightsConfigEntry
) -> bool:
    """Set up Homeassistant Analytics from a config entry."""
    client = HomeassistantAnalyticsClient(session=async_get_clientsession(hass))

    try:
        integrations = await client.get_integrations()
    except HomeassistantAnalyticsConnectionError as ex:
        raise ConfigEntryNotReady("Could not fetch integration list") from ex

    names = {}
    for integration in entry.options[CONF_TRACKED_INTEGRATIONS]:
        if integration not in integrations:
            names[integration] = integration
            continue
        names[integration] = integrations[integration].title

    coordinator = HomeassistantAnalyticsDataUpdateCoordinator(hass, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AnalyticsInsightsData(coordinator=coordinator, names=names)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AnalyticsInsightsConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(
    hass: HomeAssistant, entry: AnalyticsInsightsConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
