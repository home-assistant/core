"""Hue sensor entities."""
from aiohue.v1.sensors import (
    TYPE_ZLL_LIGHTLEVEL,
    TYPE_ZLL_ROTARY,
    TYPE_ZLL_SWITCH,
    TYPE_ZLL_TEMPERATURE,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import LIGHT_LUX, PERCENTAGE, TEMP_CELSIUS
from homeassistant.helpers.entity import EntityCategory

from ..const import DOMAIN as HUE_DOMAIN
from .sensor_base import SENSOR_CONFIG_MAP, GenericHueSensor, GenericZLLSensor

LIGHT_LEVEL_NAME_FORMAT = "{} light level"
REMOTE_NAME_FORMAT = "{} battery level"
TEMPERATURE_NAME_FORMAT = "{} temperature"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    bridge = hass.data[HUE_DOMAIN][config_entry.entry_id]

    if not bridge.sensor_manager:
        return

    await bridge.sensor_manager.async_register_component("sensor", async_add_entities)


class GenericHueGaugeSensorEntity(GenericZLLSensor, SensorEntity):
    """Parent class for all 'gauge' Hue device sensors."""


class HueLightLevel(GenericHueGaugeSensorEntity):
    """The light level sensor entity for a Hue motion sensor device."""

    _attr_device_class = SensorDeviceClass.ILLUMINANCE
    _attr_native_unit_of_measurement = LIGHT_LUX

    @property
    def native_value(self):
        """Return the state of the device."""
        if self.sensor.lightlevel is None:
            return None

        # https://developers.meethue.com/develop/hue-api/supported-devices/#clip_zll_lightlevel
        # Light level in 10000 log10 (lux) +1 measured by sensor. Logarithm
        # scale used because the human eye adjusts to light levels and small
        # changes at low lux levels are more noticeable than at high lux
        # levels.
        return round(float(10 ** ((self.sensor.lightlevel - 1) / 10000)), 2)

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        attributes = super().extra_state_attributes
        attributes.update(
            {
                "lightlevel": self.sensor.lightlevel,
                "daylight": self.sensor.daylight,
                "dark": self.sensor.dark,
                "threshold_dark": self.sensor.tholddark,
                "threshold_offset": self.sensor.tholdoffset,
            }
        )
        return attributes


class HueTemperature(GenericHueGaugeSensorEntity):
    """The temperature sensor entity for a Hue motion sensor device."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = TEMP_CELSIUS

    @property
    def native_value(self):
        """Return the state of the device."""
        if self.sensor.temperature is None:
            return None

        return self.sensor.temperature / 100


class HueBattery(GenericHueSensor, SensorEntity):
    """Battery class for when a batt-powered device is only represented as an event."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self):
        """Return a unique identifier for this device."""
        return f"{self.sensor.uniqueid}-battery"

    @property
    def native_value(self):
        """Return the state of the battery."""
        return self.sensor.battery


SENSOR_CONFIG_MAP.update(
    {
        TYPE_ZLL_LIGHTLEVEL: {
            "platform": "sensor",
            "name_format": LIGHT_LEVEL_NAME_FORMAT,
            "class": HueLightLevel,
        },
        TYPE_ZLL_TEMPERATURE: {
            "platform": "sensor",
            "name_format": TEMPERATURE_NAME_FORMAT,
            "class": HueTemperature,
        },
        TYPE_ZLL_SWITCH: {
            "platform": "sensor",
            "name_format": REMOTE_NAME_FORMAT,
            "class": HueBattery,
        },
        TYPE_ZLL_ROTARY: {
            "platform": "sensor",
            "name_format": REMOTE_NAME_FORMAT,
            "class": HueBattery,
        },
    }
)
