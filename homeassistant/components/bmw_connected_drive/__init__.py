"""Reads vehicle status from MyBMW portal."""

from __future__ import annotations

import logging
from typing import Any

from bimmer_connected.vehicle import MyBMWVehicle
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_ENTITY_ID, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    discovery,
    entity_registry as er,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_VIN, ATTRIBUTION, CONF_READ_ONLY, DATA_HASS_CONFIG, DOMAIN
from .coordinator import BMWDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the BMW Connected Drive component from configuration.yaml."""
    # Store full yaml config in data for platform.NOTIFY
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][DATA_HASS_CONFIG] = config

    return True


@callback
def _async_migrate_options_from_data_if_missing(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    data = dict(entry.data)
    options = dict(entry.options)

    if CONF_READ_ONLY in data or list(options) != list(DEFAULT_OPTIONS):
        options = dict(DEFAULT_OPTIONS, **options)
        options[CONF_READ_ONLY] = data.pop(CONF_READ_ONLY, False)

        hass.config_entries.async_update_entry(entry, data=data, options=options)


async def _async_migrate_entries(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Migrate old entry."""
    entity_registry = er.async_get(hass)

    @callback
    def update_unique_id(entry: er.RegistryEntry) -> dict[str, str] | None:
        replacements = {
            "charging_level_hv": "remaining_battery_percent",
            "fuel_percent": "remaining_fuel_percent",
        }
        if (key := entry.unique_id.split("-")[-1]) in replacements:
            new_unique_id = entry.unique_id.replace(key, replacements[key])
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BMW Connected Drive from a config entry."""

    _async_migrate_options_from_data_if_missing(hass, entry)

    await _async_migrate_entries(hass, entry)

    # Set up one data coordinator per account/config entry
    coordinator = BMWDataUpdateCoordinator(
        hass,
        entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

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
            hass.data[DOMAIN][DATA_HASS_CONFIG],
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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class BMWBaseEntity(CoordinatorEntity[BMWDataUpdateCoordinator]):
    """Common base for BMW entities."""

    coordinator: BMWDataUpdateCoordinator
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: MyBMWVehicle,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)

        self.vehicle = vehicle

        self._attrs: dict[str, Any] = {
            "car": self.vehicle.name,
            "vin": self.vehicle.vin,
        }
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.vehicle.vin)},
            manufacturer=vehicle.brand.name,
            model=vehicle.name,
            name=vehicle.name,
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
