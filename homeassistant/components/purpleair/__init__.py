"""The PurpleAir integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_SENSOR_INDEX,
    CONF_SENSOR_INDICES,
    CONF_SENSOR_LIST,
    SCHEMA_VERSION,
)
from .coordinator import (
    PurpleAirConfigEntry,
    PurpleAirDataUpdateCoordinator,
    SensorConfigList,
)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    """Set up PurpleAir config entry."""
    coordinator = PurpleAirDataUpdateCoordinator(
        hass,
        entry,
    )
    entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    coordinator.async_delete_orphans_from_device_registry()

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    """Migrate config entry."""
    # v1 stored sensor indexes in config_entry.options[CONF_SENSOR_INDICES] as list[int]
    # v2 stores sensor indexes in config_entry.data[CONF_SENSOR_LIST] as type SensorConfigList = list[dict[str, any]]
    if entry.version == 1:
        new_options = entry.options.copy()
        new_options.pop(CONF_SENSOR_INDICES, None)

        index_list: list[int] = entry.options[CONF_SENSOR_INDICES]
        sensor_list: SensorConfigList = [
            {CONF_SENSOR_INDEX: int(sensor_index)} for sensor_index in index_list
        ]
        new_data = entry.data.copy()
        new_data[CONF_SENSOR_LIST] = sensor_list

        hass.config_entries.async_update_entry(
            entry, data=new_data, options=new_options, version=SCHEMA_VERSION
        )

    return True


async def async_reload_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
