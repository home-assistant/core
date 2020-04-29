"""Hue binary sensor entities."""

from aiohue.sensors import TYPE_ZLL_PRESENCE

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    BinarySensorDevice,
)

from .const import DOMAIN as HUE_DOMAIN
from .sensor_base import SENSOR_CONFIG_MAP, GenericZLLSensor

PRESENCE_NAME_FORMAT = "{} motion"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer binary sensor setup to the shared sensor module."""
    await hass.data[HUE_DOMAIN][
        config_entry.entry_id
    ].sensor_manager.async_register_component("binary_sensor", async_add_entities)


class HuePresence(GenericZLLSensor, BinarySensorDevice):
    """The presence sensor entity for a Hue motion sensor device."""

    device_class = DEVICE_CLASS_MOTION

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.sensor.presence

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = super().device_state_attributes
        if "sensitivity" in self.sensor.config:
            attributes["sensitivity"] = self.sensor.config["sensitivity"]
        if "sensitivitymax" in self.sensor.config:
            attributes["sensitivity_max"] = self.sensor.config["sensitivitymax"]
        return attributes


SENSOR_CONFIG_MAP.update(
    {
        TYPE_ZLL_PRESENCE: {
            "platform": "binary_sensor",
            "name_format": PRESENCE_NAME_FORMAT,
            "class": HuePresence,
        }
    }
)
