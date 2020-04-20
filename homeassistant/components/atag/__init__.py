"""The ATAG Integration."""
from datetime import timedelta
import logging

import async_timeout
from pyatag import AtagDataStore, AtagException

from homeassistant.components.climate import DOMAIN as CLIMATE
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_ID,
    ATTR_MODE,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PRESSURE_BAR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, asyncio
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

DOMAIN = "atag"
DATA_LISTENER = f"{DOMAIN}_listener"
SIGNAL_UPDATE_ATAG = f"{DOMAIN}_update"
PLATFORMS = [CLIMATE, WATER_HEATER, SENSOR]
HOUR = "h"
FIRE = "fire"
PERCENTAGE = "%"

ICONS = {
    TEMP_CELSIUS: "mdi:thermometer",
    PRESSURE_BAR: "mdi:gauge",
    FIRE: "mdi:fire",
    ATTR_MODE: "mdi:settings",
}

ENTITY_TYPES = {
    SENSOR: [
        {
            ATTR_NAME: "Outside Temperature",
            ATTR_ID: "outside_temp",
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
            ATTR_ICON: ICONS[TEMP_CELSIUS],
        },
        {
            ATTR_NAME: "Average Outside Temperature",
            ATTR_ID: "tout_avg",
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
            ATTR_ICON: ICONS[TEMP_CELSIUS],
        },
        {
            ATTR_NAME: "Weather Status",
            ATTR_ID: "weather_status",
            ATTR_UNIT_OF_MEASUREMENT: None,
            ATTR_DEVICE_CLASS: None,
            ATTR_ICON: None,
        },
        {
            ATTR_NAME: "CH Water Pressure",
            ATTR_ID: "ch_water_pres",
            ATTR_UNIT_OF_MEASUREMENT: PRESSURE_BAR,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
            ATTR_ICON: ICONS[PRESSURE_BAR],
        },
        {
            ATTR_NAME: "CH Water Temperature",
            ATTR_ID: "ch_water_temp",
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
            ATTR_ICON: ICONS[TEMP_CELSIUS],
        },
        {
            ATTR_NAME: "CH Return Temperature",
            ATTR_ID: "ch_return_temp",
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
            ATTR_ICON: ICONS[TEMP_CELSIUS],
        },
        {
            ATTR_NAME: "Burning Hours",
            ATTR_ID: "burning_hours",
            ATTR_UNIT_OF_MEASUREMENT: HOUR,
            ATTR_DEVICE_CLASS: None,
            ATTR_ICON: ICONS[FIRE],
        },
        {
            ATTR_NAME: "Flame",
            ATTR_ID: "rel_mod_level",
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            ATTR_DEVICE_CLASS: None,
            ATTR_ICON: ICONS[FIRE],
        },
    ],
    CLIMATE: {
        ATTR_NAME: DOMAIN.title(),
        ATTR_ID: CLIMATE,
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: None,
    },
    WATER_HEATER: {
        ATTR_NAME: DOMAIN.title(),
        ATTR_ID: WATER_HEATER,
        ATTR_UNIT_OF_MEASUREMENT: None,
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: None,
    },
}


async def async_setup(hass: HomeAssistant, config):
    """Set up the Atag component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Atag integration from a config entry."""
    session = async_get_clientsession(hass)

    coordinator = AtagDataUpdateCoordinator(hass, session, entry)

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


class AtagDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold Atag data."""

    def __init__(self, hass, session, entry):
        """Initialize."""
        self.atag = AtagDataStore(session, paired=True, **entry.data)

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=30)
        )

    async def _async_update_data(self):
        """Update data via library."""
        with async_timeout.timeout(20):
            try:
                await self.atag.async_update()
            except (AtagException) as error:
                raise UpdateFailed(error)

        return self.atag.sensordata


async def async_unload_entry(hass, entry):
    """Unload Atag config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class AtagEntity(Entity):
    """Defines a base Atag entity."""

    def __init__(self, coordinator: AtagDataUpdateCoordinator, atag_type: dict) -> None:
        """Initialize the Atag entity."""
        self.coordinator = coordinator

        self._id = atag_type[ATTR_ID]
        self._name = atag_type[ATTR_NAME]
        self._icon = atag_type[ATTR_ICON]
        self._unit = atag_type[ATTR_UNIT_OF_MEASUREMENT]
        self._class = atag_type[ATTR_DEVICE_CLASS]

    @property
    def device_info(self) -> dict:
        """Return info for device registry."""
        device = self.coordinator.atag.device
        version = self.coordinator.atag.apiversion
        return {
            "identifiers": {(DOMAIN, device)},
            ATTR_NAME: "Atag Thermostat",
            "model": "Atag One",
            "sw_version": version,
            "manufacturer": "Atag",
        }

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        self._icon = (
            self.coordinator.data.get(self._id, {}).get(ATTR_ICON) or self._icon
        )
        return self._icon

    @property
    def should_poll(self) -> bool:
        """Return the polling requirement of the entity."""
        return False

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @property
    def device_class(self):
        """Return the device class."""
        return self._class

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return f"{self.coordinator.atag.device}-{self._id}"

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update Atag entity."""
        await self.coordinator.async_request_refresh()
