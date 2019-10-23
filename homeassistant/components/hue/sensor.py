"""Hue sensor entities."""
from aiohue.sensors import TYPE_ZLL_LIGHTLEVEL, TYPE_ZLL_TEMPERATURE

from homeassistant.components.hue.sensor_base import (
    GenericZLLSensor,
    SensorManager,
    async_setup_entry as shared_async_setup_entry,
)
from homeassistant.const import (
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
)
from homeassistant.helpers.entity import Entity

LIGHT_LEVEL_NAME_FORMAT = "{} light level"
TEMPERATURE_NAME_FORMAT = "{} temperature"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    SensorManager.sensor_config_map.update(
        {
            TYPE_ZLL_LIGHTLEVEL: {
                "binary": False,
                "name_format": LIGHT_LEVEL_NAME_FORMAT,
                "class": HueLightLevel,
            },
            TYPE_ZLL_TEMPERATURE: {
                "binary": False,
                "name_format": TEMPERATURE_NAME_FORMAT,
                "class": HueTemperature,
            },
        }
    )
    await shared_async_setup_entry(hass, config_entry, async_add_entities, binary=False)


class GenericHueGaugeSensorEntity(GenericZLLSensor, Entity):
    """Parent class for all 'gauge' Hue device sensors."""

    async def _async_update_ha_state(self, *args, **kwargs):
        await self.async_update_ha_state(self, *args, **kwargs)


class HueLightLevel(GenericHueGaugeSensorEntity):
    """The light level sensor entity for a Hue motion sensor device."""

    device_class = DEVICE_CLASS_ILLUMINANCE
    unit_of_measurement = "lx"

    @property
    def state(self):
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
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = super().device_state_attributes
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

    device_class = DEVICE_CLASS_TEMPERATURE
    unit_of_measurement = TEMP_CELSIUS

    @property
    def state(self):
        """Return the state of the device."""
        if self.sensor.temperature is None:
            return None

        return self.sensor.temperature / 100
