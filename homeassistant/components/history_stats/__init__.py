"""The history_stats component."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID, CONF_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device import (
    async_entity_id_to_device_id,
    async_remove_stale_devices_links_keep_entity_device,
)
from homeassistant.helpers.helper_integration import (
    async_handle_source_entity_changes,
    async_remove_helper_config_entry_from_source_device,
)
from homeassistant.helpers.template import Template

from .const import CONF_DURATION, CONF_END, CONF_START, PLATFORMS
from .coordinator import HistoryStatsUpdateCoordinator
from .data import HistoryStats

type HistoryStatsConfigEntry = ConfigEntry[HistoryStatsUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)


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

    # This can be removed in HA Core 2026.2
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
        hass.config_entries.async_schedule_reload(entry.entry_id)

    async def source_entity_removed() -> None:
        # The source entity has been removed, we remove the config entry because
        # history_stats does not allow replacing the input entity.
        await hass.config_entries.async_remove(entry.entry_id)

    entry.async_on_unload(
        async_handle_source_entity_changes(
            hass,
            add_helper_config_entry_to_device=False,
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

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating from version %s.%s", config_entry.version, config_entry.minor_version
    )

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False
    if config_entry.version == 1:
        options = {**config_entry.options}
        if config_entry.minor_version < 2:
            # Remove the history_stats config entry from the source device
            if source_device_id := async_entity_id_to_device_id(
                hass, options[CONF_ENTITY_ID]
            ):
                async_remove_helper_config_entry_from_source_device(
                    hass,
                    helper_config_entry_id=config_entry.entry_id,
                    source_device_id=source_device_id,
                )
        hass.config_entries.async_update_entry(
            config_entry, options=options, minor_version=2
        )

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HistoryStatsConfigEntry
) -> bool:
    """Unload History stats config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
