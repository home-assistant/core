"""The trafikverket_train component."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import PLATFORMS
from .coordinator import TVDataUpdateCoordinator

TVTrainConfigEntry = ConfigEntry[TVDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TVTrainConfigEntry) -> bool:
    """Set up Trafikverket Train from a config entry."""

    coordinator = TVDataUpdateCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entity_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_reg, entry.entry_id)
    for entity in entries:
        if not entity.unique_id.startswith(entry.entry_id):
            entity_reg.async_update_entity(
                entity.entity_id, new_unique_id=f"{entry.entry_id}-departure_time"
            )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Trafikverket Weatherstation config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
