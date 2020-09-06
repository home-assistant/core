"""Representation of Z-Wave sensors."""

import logging

from openzwavemqtt.const import CommandClass

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DOMAIN as SENSOR_DOMAIN,
)
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_UNSUBSCRIBE, DOMAIN
from .entity import ZWaveDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave sensor from config entry."""

    @callback
    def async_add_sensor(value):
        """Add Z-Wave Sensor."""
        # Basic Sensor types
        if isinstance(value.primary.value, (float, int)):
            sensor = ZWaveNumericSensor(value)

        elif isinstance(value.primary.value, dict):
            sensor = ZWaveListSensor(value)

        elif isinstance(value.primary.value, str):
            sensor = ZWaveStringSensor(value)

        else:
            _LOGGER.warning("Sensor not implemented for value %s", value.primary.label)
            return

        async_add_entities([sensor])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_new_{SENSOR_DOMAIN}", async_add_sensor
        )
    )


class ZwaveSensorBase(ZWaveDeviceEntity):
    """Basic Representation of a Z-Wave sensor."""

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self.values.primary.command_class == CommandClass.BATTERY:
            return DEVICE_CLASS_BATTERY
        if self.values.primary.command_class == CommandClass.METER:
            return DEVICE_CLASS_POWER
        if "Temperature" in self.values.primary.label:
            return DEVICE_CLASS_TEMPERATURE
        if "Illuminance" in self.values.primary.label:
            return DEVICE_CLASS_ILLUMINANCE
        if "Humidity" in self.values.primary.label:
            return DEVICE_CLASS_HUMIDITY
        if "Power" in self.values.primary.label:
            return DEVICE_CLASS_POWER
        if "Energy" in self.values.primary.label:
            return DEVICE_CLASS_POWER
        if "Electric" in self.values.primary.label:
            return DEVICE_CLASS_POWER
        if "Pressure" in self.values.primary.label:
            return DEVICE_CLASS_PRESSURE
        return None

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # We hide some of the more advanced sensors by default to not overwhelm users
        if self.values.primary.command_class in [
            CommandClass.BASIC,
            CommandClass.INDICATOR,
            CommandClass.NOTIFICATION,
        ]:
            return False
        return True

    @property
    def force_update(self) -> bool:
        """Force updates."""
        return True


class ZWaveStringSensor(ZwaveSensorBase):
    """Representation of a Z-Wave sensor."""

    @property
    def state(self):
        """Return state of the sensor."""
        return self.values.primary.value

    @property
    def unit_of_measurement(self):
        """Return unit of measurement the value is expressed in."""
        return self.values.primary.units

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return False


class ZWaveNumericSensor(ZwaveSensorBase):
    """Representation of a Z-Wave sensor."""

    @property
    def state(self):
        """Return state of the sensor."""
        return round(self.values.primary.value, 2)

    @property
    def unit_of_measurement(self):
        """Return unit of measurement the value is expressed in."""
        if self.values.primary.units == "C":
            return TEMP_CELSIUS
        if self.values.primary.units == "F":
            return TEMP_FAHRENHEIT

        return self.values.primary.units


class ZWaveListSensor(ZwaveSensorBase):
    """Representation of a Z-Wave list sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        # We use the id as value for backwards compatibility
        return self.values.primary.value["Selected_id"]

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        attributes = super().device_state_attributes
        # add the value's label as property
        attributes["label"] = self.values.primary.value["Selected"]
        return attributes

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # these sensors are only here for backwards compatibility, disable them by default
        return False
