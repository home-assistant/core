"""Reads vehicle status from MyBMW portal."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_ENTITY_ID, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    discovery,
    entity_registry as er,
)
import homeassistant.helpers.config_validation as cv

from .const import ATTR_VIN, CONF_READ_ONLY, DOMAIN
from .coordinator import BMWConfigEntry, BMWDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


SERVICE_SCHEMA = vol.Schema(
    vol.Any(
        {vol.Required(ATTR_VIN): cv.string},
        {vol.Required(CONF_DEVICE_ID): cv.string},
    )
)

DEFAULT_OPTIONS = {
    CONF_READ_ONLY: False,
}

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.NOTIFY,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

SERVICE_UPDATE_STATE = "update_state"


@callback
def _async_migrate_options_from_data_if_missing(
    hass: HomeAssistant, entry: BMWConfigEntry
) -> None:
    data = dict(entry.data)
    options = dict(entry.options)

    if CONF_READ_ONLY in data or list(options) != list(DEFAULT_OPTIONS):
        options = dict(
            DEFAULT_OPTIONS,
            **{k: v for k, v in options.items() if k in DEFAULT_OPTIONS},
        )
        options[CONF_READ_ONLY] = data.pop(CONF_READ_ONLY, False)

        hass.config_entries.async_update_entry(entry, data=data, options=options)


async def _async_migrate_entries(
    hass: HomeAssistant, config_entry: BMWConfigEntry
) -> bool:
    """Migrate old entry."""
    entity_registry = er.async_get(hass)

    @callback
    def update_unique_id(entry: er.RegistryEntry) -> dict[str, str] | None:
        replacements = {
            Platform.SENSOR.value: {
                "charging_level_hv": "fuel_and_battery.remaining_battery_percent",
                "fuel_percent": "fuel_and_battery.remaining_fuel_percent",
                "ac_current_limit": "charging_profile.ac_current_limit",
                "charging_start_time": "fuel_and_battery.charging_start_time",
                "charging_end_time": "fuel_and_battery.charging_end_time",
                "charging_status": "fuel_and_battery.charging_status",
                "charging_target": "fuel_and_battery.charging_target",
                "remaining_battery_percent": "fuel_and_battery.remaining_battery_percent",
                "remaining_range_total": "fuel_and_battery.remaining_range_total",
                "remaining_range_electric": "fuel_and_battery.remaining_range_electric",
                "remaining_range_fuel": "fuel_and_battery.remaining_range_fuel",
                "remaining_fuel": "fuel_and_battery.remaining_fuel",
                "remaining_fuel_percent": "fuel_and_battery.remaining_fuel_percent",
                "activity": "climate.activity",
            }
        }
        if (key := entry.unique_id.split("-")[-1]) in replacements.get(
            entry.domain, []
        ):
            new_unique_id = entry.unique_id.replace(
                key, replacements[entry.domain][key]
            )
            _LOGGER.debug(
                "Migrating entity '%s' unique_id from '%s' to '%s'",
                entry.entity_id,
                entry.unique_id,
                new_unique_id,
            )
            if existing_entity_id := entity_registry.async_get_entity_id(
                entry.domain, entry.platform, new_unique_id
            ):
                _LOGGER.debug(
                    "Cannot migrate to unique_id '%s', already exists for '%s'",
                    new_unique_id,
                    existing_entity_id,
                )
                return None
            return {
                "new_unique_id": new_unique_id,
            }
        return None

    await er.async_migrate_entries(hass, config_entry.entry_id, update_unique_id)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: BMWConfigEntry) -> bool:
    """Set up BMW Connected Drive from a config entry."""

    _async_migrate_options_from_data_if_missing(hass, entry)

    await _async_migrate_entries(hass, entry)

    # Set up one data coordinator per account/config entry
    coordinator = BMWDataUpdateCoordinator(
        hass,
        config_entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Set up all platforms except notify
    await hass.config_entries.async_forward_entry_setups(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )

    # set up notify platform, no entry support for notify platform yet,
    # have to use discovery to load platform.
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {CONF_NAME: DOMAIN, CONF_ENTITY_ID: entry.entry_id},
            {},
        )
    )

    # Clean up vehicles which are not assigned to the account anymore
    account_vehicles = {(DOMAIN, v.vin) for v in coordinator.account.vehicles}
    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry_id=entry.entry_id
    )
    for device in device_entries:
        if not device.identifiers.intersection(account_vehicles):
            device_registry.async_update_device(
                device.id, remove_config_entry_id=entry.entry_id
            )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BMWConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )
