"""The Kaiterra integration."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, CONF_DEVICE_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api_data import KaiterraApiClient
from .const import CONF_AQI_STANDARD, DEFAULT_AQI_STANDARD, DOMAIN, LOGGER, PLATFORMS
from .coordinator import KaiterraConfigEntry, KaiterraDataUpdateCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _async_remove_legacy_air_quality_entity(
    hass: HomeAssistant, entry: KaiterraConfigEntry
) -> None:
    """Remove the legacy air quality entity registry entry."""
    entity_registry = er.async_get(hass)
    old_unique_id = f"{entry.unique_id}_air_quality"

    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity_entry.unique_id == old_unique_id:
            entity_registry.async_remove(entity_entry.entity_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Kaiterra from configuration.yaml."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: KaiterraConfigEntry) -> bool:
    """Set up Kaiterra from a config entry."""
    _async_remove_legacy_air_quality_entity(hass, entry)

    coordinator = KaiterraDataUpdateCoordinator(
        hass,
        entry,
        KaiterraApiClient(
            async_get_clientsession(hass),
            entry.data[CONF_API_KEY],
            entry.options.get(CONF_AQI_STANDARD, DEFAULT_AQI_STANDARD),
        ),
        entry.data[CONF_DEVICE_ID],
        entry.data.get(CONF_NAME) or entry.title,
    )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_update_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_update_entry(hass: HomeAssistant, entry: KaiterraConfigEntry) -> None:
    """Reload the entry when it is updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: KaiterraConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: KaiterraConfigEntry) -> bool:
    """Migrate old config entries."""
    if entry.version > 1:
        return False

    version = entry.version
    minor_version = entry.minor_version

    if version == 1 and minor_version == 1:
        _async_remove_legacy_air_quality_entity(hass, entry)
        hass.config_entries.async_update_entry(entry, minor_version=2)
        LOGGER.debug("Migration to version %s.%s successful", version, 2)

    return True
