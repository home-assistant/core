"""The history_stats component."""

from datetime import timedelta
import logging

from homeassistant.components.sensor import CONF_STATE_CLASS, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID, CONF_STATE, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device import async_entity_id_to_device_id
from homeassistant.helpers.helper_integration import (
    async_handle_source_entity_changes,
    async_remove_helper_devices,
)
from homeassistant.helpers.template import Template

from .const import (
    CONF_MIN_STATE_DURATION,
    CONF_PERIOD,
    DOMAIN,
    PLATFORMS,
    SECTION_ADDITIONAL_SETTINGS,
    Period,
)
from .coordinator import HistoryStatsUpdateCoordinator
from .data import HistoryStats
from .helpers import resolve_period_config

type HistoryStatsConfigEntry = ConfigEntry[HistoryStatsUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "DOMAIN",
]


async def async_setup_entry(
    hass: HomeAssistant, entry: HistoryStatsConfigEntry
) -> None:
    """Set up History stats from a config entry."""

    entity_id: str = entry.options[CONF_ENTITY_ID]
    entity_states: list[str] = entry.options[CONF_STATE]
    period_config = resolve_period_config(entry.options, entry.options[CONF_TYPE])

    min_state_duration: timedelta
    additional_settings = entry.options.get(SECTION_ADDITIONAL_SETTINGS, {})
    if min_state_duration_dict := additional_settings.get(CONF_MIN_STATE_DURATION):
        min_state_duration = timedelta(**min_state_duration_dict)
    else:
        min_state_duration = timedelta(0)

    history_stats = HistoryStats(
        hass,
        entity_id,
        entity_states,
        Template(period_config.start, hass) if period_config.start else None,
        Template(period_config.end, hass) if period_config.end else None,
        period_config.duration,
        min_state_duration,
    )
    coordinator = HistoryStatsUpdateCoordinator(hass, history_stats, entry, entry.title)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

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


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: HistoryStatsConfigEntry
) -> None:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating from version %s.%s", config_entry.version, config_entry.minor_version
    )

    if config_entry.version == 1:
        options = {**config_entry.options}
        if config_entry.minor_version < 2:
            # Remove the history_stats config entry from the source device
            if source_device_id := async_entity_id_to_device_id(
                hass, options[CONF_ENTITY_ID]
            ):
                async_remove_helper_devices(
                    hass,
                    helper_config_entry_id=config_entry.entry_id,
                    source_device_id=source_device_id,
                )
        hass.config_entries.async_update_entry(
            config_entry, options=options, minor_version=2
        )
        if config_entry.minor_version < 3:
            # Set the state class to measurement for backward compatibility
            options[CONF_STATE_CLASS] = SensorStateClass.MEASUREMENT
        hass.config_entries.async_update_entry(
            config_entry, options=options, minor_version=3
        )
        # The "advanced_settings" section was renamed to "additional_settings"
        if (additional := options.pop("advanced_settings", None)) is not None:
            options[SECTION_ADDITIONAL_SETTINGS] = additional
        hass.config_entries.async_update_entry(
            config_entry, options=options, version=2, minor_version=1
        )

    if config_entry.version == 2 and config_entry.minor_version < 2:
        # Entries created before period presets keep their custom period
        hass.config_entries.async_update_entry(
            config_entry,
            options={**config_entry.options, CONF_PERIOD: Period.CUSTOM},
            minor_version=2,
        )

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )


async def async_unload_entry(
    hass: HomeAssistant, entry: HistoryStatsConfigEntry
) -> None:
    """Unload History stats config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
