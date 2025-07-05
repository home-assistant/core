"""PurpleAir integration."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Final

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_SHOW_ON_MAP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_SENSOR, CONF_SENSOR_INDEX, DOMAIN, LOGGER, SCHEMA_VERSION, TITLE
from .coordinator import PurpleAirConfigEntry, PurpleAirDataUpdateCoordinator

PLATFORMS: Final[list[str]] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    """Set up config entry."""
    coordinator = PurpleAirDataUpdateCoordinator(
        hass,
        entry,
    )
    entry.runtime_data = coordinator

    if len(entry.subentries) > 0:
        await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    """Migrate config entry."""
    if entry.version == SCHEMA_VERSION:
        return True

    if entry.version != 1:
        LOGGER.error("Unsupported schema version %s", entry.version)
        return False

    LOGGER.info("Migrating schema version from %s to %s", entry.version, SCHEMA_VERSION)

    CONF_SENSOR_INDICES: Final[str] = "sensor_indices"
    index_list: Any | None = entry.options.get(CONF_SENSOR_INDICES)

    if not index_list or type(index_list) is not list or len(index_list) == 0:
        LOGGER.warning("No sensors registered in configuration")
        return hass.config_entries.async_update_entry(
            entry,
            version=SCHEMA_VERSION,
        )

    dev_reg = dr.async_get(hass)
    dev_list = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    for device in dev_list:
        identifiers = (
            int(identifier[1])
            for identifier in device.identifiers
            if identifier[0] == DOMAIN
        )
        sensor_index = next(identifiers, None)
        assert sensor_index in index_list, "Sensor not in config entry"

        dev_reg.async_remove_device(device.id)

        # Keep subentry logic in sync with subentry_flow.py:async_step_select_sensor()
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType({CONF_SENSOR_INDEX: sensor_index}),
                subentry_type=CONF_SENSOR,
                title=f"{device.name} ({sensor_index})",
                unique_id=str(sensor_index),
            ),
        )

    # Keep entry logic in sync with config_flow.py:async_step_api_key()
    title: str = TITLE
    config_list = hass.config_entries.async_entries(
        domain=DOMAIN, include_disabled=True, include_ignore=True
    )
    if len(config_list) > 1:
        title = f"{TITLE} ({entry.title})"

    return hass.config_entries.async_update_entry(
        entry,
        title=title,
        unique_id=entry.data[CONF_API_KEY],
        data={CONF_API_KEY: entry.data[CONF_API_KEY]},
        options={CONF_SHOW_ON_MAP: entry.options.get(CONF_SHOW_ON_MAP, False)},
        version=SCHEMA_VERSION,
    )


async def async_reload_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PurpleAirConfigEntry) -> bool:
    """Unload config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
