"""Reads vehicle status from BMW connected drive portal."""
from __future__ import annotations

from typing import Any

from bimmer_connected.vehicle import ConnectedDriveVehicle
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_REGION,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_VIN, ATTRIBUTION, CONF_READ_ONLY, DATA_HASS_CONFIG, DOMAIN
from .coordinator import BMWDataUpdateCoordinator

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
    Platform.SENSOR,
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BMW Connected Drive from a config entry."""

    _async_migrate_options_from_data_if_missing(hass, entry)

    # Set up one data coordinator per account/config entry
    coordinator = BMWDataUpdateCoordinator(
        hass,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        region=entry.data[CONF_REGION],
        read_only=entry.options[CONF_READ_ONLY],
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up all platforms except notify
    hass.config_entries.async_setup_platforms(
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

    # Add event listener for option flow changes
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [platform for platform in PLATFORMS if platform != Platform.NOTIFY]
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_options(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class BMWConnectedDriveBaseEntity(CoordinatorEntity[BMWDataUpdateCoordinator], Entity):
    """Common base for BMW entities."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: ConnectedDriveVehicle,
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
            name=f"{vehicle.brand.name} {vehicle.name}",
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
