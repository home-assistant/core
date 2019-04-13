"""Hue sensor entities."""
from homeassistant.const import (
    DEVICE_CLASS_ILLUMINANCE, DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity
from homeassistant.components.hue.sensor_base import (
    GenericZLLSensor, async_setup_entry as shared_async_setup_entry)


LIGHT_LEVEL_NAME_FORMAT = "{} light level"
TEMPERATURE_NAME_FORMAT = "{} temperature"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    await shared_async_setup_entry(
        hass, config_entry, async_add_entities, binary=False)


class GenericHueGaugeSensorEntity(GenericZLLSensor, Entity):
    """Parent class for all 'gauge' Hue device sensors."""

    async def _async_update_ha_state(self, *args, **kwargs):
        await self.async_update_ha_state(self, *args, **kwargs)


class HueLightLevel(GenericHueGaugeSensorEntity):
    """The light level sensor entity for a Hue motion sensor device."""

    device_class = DEVICE_CLASS_ILLUMINANCE
    unit_of_measurement = "Lux"

    @property
    def state(self):
        """Return the state of the device."""
        return self.sensor.lightlevel

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = super().device_state_attributes
        attributes.update({
            "threshold_dark": self.sensor.tholddark,
            "threshold_offset": self.sensor.tholdoffset,
        })
        return attributes


class HueTemperature(GenericHueGaugeSensorEntity):
    """The temperature sensor entity for a Hue motion sensor device."""

    device_class = DEVICE_CLASS_TEMPERATURE
    unit_of_measurement = TEMP_CELSIUS

    @property
    def state(self):
        """Return the state of the device."""
        return self.sensor.temperature / 100
