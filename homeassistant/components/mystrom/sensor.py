"""Support for myStrom sensors of switches/plugs."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER

DEFAULT_NAME = "myStrom Switch"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the myStrom entities."""
    device = hass.data[DOMAIN][entry.entry_id].device
    async_add_entities(
        [
            MyStromSwitchConsumptionSensor(device, entry.title),
            MyStromSwitchTemperatureSensor(device, entry.title),
        ]
    )


class MyStromSwitchConsumptionSensor(SensorEntity):
    """Representation of the consumption of a myStrom switch/plug."""

    _attr_has_entity_name = True
    _attr_name = "Power"

    def __init__(self, device, name):
        """Initialize the sensor."""
        self.device = device
        self._attr_unique_id = self.device.mac + "_consumption"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device.mac)},
            name=name,
            manufacturer=MANUFACTURER,
            sw_version=self.device.firmware,
        )

    async def async_update(self) -> None:
        """Get the latest data from the device and update the data."""
        self._attr_native_value = self.device.consumption


class MyStromSwitchTemperatureSensor(SensorEntity):
    """Representation of the temperature of a myStrom switch/plug."""

    _attr_has_entity_name = True
    _attr_name = "Temperature"

    def __init__(self, device, name):
        """Initialize the sensor."""
        self.device = device
        self._attr_unique_id = self.device.mac + "_temperature"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device.mac)},
            name=name,
            manufacturer=MANUFACTURER,
            sw_version=self.device.firmware,
        )

    async def async_update(self) -> None:
        """Get the latest data from the device and update the data. Note: the actual fetching happens in the 'main' entity, the switch itself."""
        self._attr_native_value = self.device.temperature
