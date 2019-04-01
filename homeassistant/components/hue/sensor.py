"""Hue sensor entities."""
from homeassistant.const import (
    DEVICE_CLASS_ILLUMINANCE, DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity
from homeassistant.components.hue.hue_sensor import (
    GenericZLLSensor, async_setup_entry)


# No-op to trick static code analysis tools.
async_setup_entry = async_setup_entry


class HueLightLevel(GenericZLLSensor, Entity):
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


class HueTemperature(GenericZLLSensor, Entity):
    """The temperature sensor entity for a Hue motion sensor device."""

    device_class = DEVICE_CLASS_TEMPERATURE
    unit_of_measurement = TEMP_CELSIUS

    @property
    def state(self):
        """Return the state of the device."""
        return self.sensor.temperature / 100
