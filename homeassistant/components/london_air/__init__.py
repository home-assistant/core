"""The London Air integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_LOCATIONS
from .coordinator import LondonAirConfigEntry, LondonAirDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LondonAirConfigEntry) -> bool:
    """Set up London Air from a config entry."""
    coordinator = LondonAirDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    _remove_stale_entries(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LondonAirConfigEntry) -> bool:
    """Unload a London Air config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _remove_stale_entries(hass: HomeAssistant, entry: LondonAirConfigEntry) -> None:
    """Remove entities and devices for authorities no longer configured."""
    locations = set(entry.data[CONF_LOCATIONS])
    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if entity_entry.unique_id not in locations:
            entity_registry.async_remove(entity_entry.entity_id)
    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if not any(
            identifier[1] in locations for identifier in device_entry.identifiers
        ):
            device_registry.async_remove_device(device_entry.id)
