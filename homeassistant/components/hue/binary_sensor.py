"""Hue binary sensor entities."""

from aiohue.sensors import TYPE_ZLL_PRESENCE

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    BinarySensorDevice,
)
from homeassistant.components.hue.sensor_base import (
    GenericZLLSensor,
    SensorManager,
    async_setup_entry as shared_async_setup_entry,
)

PRESENCE_NAME_FORMAT = "{} motion"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer binary sensor setup to the shared sensor module."""
    SensorManager.sensor_config_map.update(
        {
            TYPE_ZLL_PRESENCE: {
                "binary": True,
                "name_format": PRESENCE_NAME_FORMAT,
                "class": HuePresence,
            }
        }
    )
    await shared_async_setup_entry(hass, config_entry, async_add_entities, binary=True)


class HuePresence(GenericZLLSensor, BinarySensorDevice):
    """The presence sensor entity for a Hue motion sensor device."""

    device_class = DEVICE_CLASS_MOTION

    async def _async_update_ha_state(self, *args, **kwargs):
        await self.async_update_ha_state(self, *args, **kwargs)

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
