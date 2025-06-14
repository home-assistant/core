"""The history_stats component."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID, CONF_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device import (
    async_entity_id_to_device_id,
    async_remove_stale_devices_links_keep_entity_device,
)
from homeassistant.helpers.helper_integration import async_handle_source_entity_changes
from homeassistant.helpers.template import Template

from .const import CONF_DURATION, CONF_END, CONF_START, PLATFORMS
from .coordinator import HistoryStatsUpdateCoordinator
from .data import HistoryStats

type HistoryStatsConfigEntry = ConfigEntry[HistoryStatsUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: HistoryStatsConfigEntry
) -> bool:
    """Set up History stats from a config entry."""

    entity_id: str = entry.options[CONF_ENTITY_ID]
    entity_states: list[str] = entry.options[CONF_STATE]
    start: str | None = entry.options.get(CONF_START)
    end: str | None = entry.options.get(CONF_END)

    duration: timedelta | None = None
    if duration_dict := entry.options.get(CONF_DURATION):
        duration = timedelta(**duration_dict)

    history_stats = HistoryStats(
        hass,
        entity_id,
        entity_states,
        Template(start, hass) if start else None,
        Template(end, hass) if end else None,
        duration,
    )
    coordinator = HistoryStatsUpdateCoordinator(hass, history_stats, entry, entry.title)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    async_remove_stale_devices_links_keep_entity_device(
        hass,
        entry.entry_id,
        entry.options[CONF_ENTITY_ID],
    )

    def set_source_entity_id_or_uuid(source_entity_id: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_ENTITY_ID: source_entity_id},
        )

    async def source_entity_removed() -> None:
        # The source entity has been removed, we remove the config entry because
        # history_stats does not allow replacing the input entity.
        await hass.config_entries.async_remove(entry.entry_id)

    entry.async_on_unload(
        async_handle_source_entity_changes(
            hass,
            helper_config_entry_id=entry.entry_id,
            set_source_entity_id_or_uuid=set_source_entity_id_or_uuid,
            source_device_id=async_entity_id_to_device_id(
                hass, entry.options[CONF_ENTITY_ID]
            ),
            source_entity_id_or_uuid=entry.options[CONF_ENTITY_ID],
            source_entity_removed=source_entity_removed,
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HistoryStatsConfigEntry
) -> bool:
    """Unload History stats config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
