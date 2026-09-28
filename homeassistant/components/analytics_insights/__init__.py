"""The Homeassistant Analytics integration."""

from dataclasses import dataclass

from python_homeassistant_analytics import (
    Environment,
    HomeassistantAnalyticsClient,
    HomeassistantAnalyticsConnectionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_TRACKED_APPS, CONF_TRACKED_INTEGRATIONS, LOGGER
from .coordinator import HomeassistantAnalyticsDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
type AnalyticsInsightsConfigEntry = ConfigEntry[AnalyticsInsightsData]


@dataclass(frozen=True)
class AnalyticsInsightsData:
    """Analytics data class."""

    coordinator: HomeassistantAnalyticsDataUpdateCoordinator
    names: dict[str, str]


async def async_setup_entry(
    hass: HomeAssistant, entry: AnalyticsInsightsConfigEntry
) -> bool:
    """Set up Homeassistant Analytics from a config entry."""
    LOGGER.debug("Setting up entry %s (options: %s)", entry.entry_id, entry.options)
    client = HomeassistantAnalyticsClient(session=async_get_clientsession(hass))

    try:
        integrations = await client.get_integrations(Environment.NEXT)
    except HomeassistantAnalyticsConnectionError as ex:
        LOGGER.warning("Fetching integration list failed: %s", ex)
        raise ConfigEntryNotReady("Could not fetch integration list") from ex
    LOGGER.debug("Fetched %s integrations", len(integrations))

    names = {}
    for integration in entry.options[CONF_TRACKED_INTEGRATIONS]:
        if integration not in integrations:
            names[integration] = integration
            continue
        names[integration] = integrations[integration].title

    coordinator = HomeassistantAnalyticsDataUpdateCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AnalyticsInsightsData(coordinator=coordinator, names=names)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    LOGGER.debug("Entry %s set up", entry.entry_id)
    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: AnalyticsInsightsConfigEntry
) -> bool:
    """Migrate to a new version."""
    # Migration for switching add-ons to apps
    if entry.version < 2:
        ent_reg = er.async_get(hass)
        for entity_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
            if not entity_entry.unique_id.startswith("addon_"):
                continue

            ent_reg.async_update_entity(
                entity_entry.entity_id,
                new_unique_id=entity_entry.unique_id.replace("addon_", "app_"),
            )

        options = dict(entry.options)
        options[CONF_TRACKED_APPS] = options.pop("tracked_addons", [])

        hass.config_entries.async_update_entry(entry, version=2, options=options)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AnalyticsInsightsConfigEntry
) -> bool:
    """Unload a config entry."""
    LOGGER.debug("Unloading entry %s", entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
