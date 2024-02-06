"""The World Air Quality Index (WAQI) integration."""
from __future__ import annotations

from aiowaqi import WAQIClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.entity_registry as er

from .const import DOMAIN
from .coordinator import WAQIDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up World Air Quality Index (WAQI) from a config entry."""

    await _migrate_unique_ids(hass, entry)

    client = WAQIClient(session=async_get_clientsession(hass))
    client.authenticate(entry.data[CONF_API_KEY])

    waqi_coordinator = WAQIDataUpdateCoordinator(hass, client)
    await waqi_coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = waqi_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _migrate_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate pre-config flow unique ids."""
    entity_registry = er.async_get(hass)
    registry_entries = er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    )
    for reg_entry in registry_entries:
        if isinstance(reg_entry.unique_id, int):  # type: ignore[unreachable]
            entity_registry.async_update_entity(  # type: ignore[unreachable]
                reg_entry.entity_id, new_unique_id=f"{reg_entry.unique_id}_air_quality"
            )
