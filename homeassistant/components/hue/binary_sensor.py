"""Hue binary sensor entities."""
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, DEVICE_CLASS_MOTION)
from homeassistant.components.hue.sensor_base import (
    GenericZLLSensor, async_setup_entry as shared_async_setup_entry)


PRESENCE_NAME_FORMAT = "{} motion"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer binary sensor setup to the shared sensor module."""
    await shared_async_setup_entry(
        hass, config_entry, async_add_entities, binary=True)


class HuePresence(GenericZLLSensor, BinarySensorDevice):
    """The presence sensor entity for a Hue motion sensor device."""

    device_class = DEVICE_CLASS_MOTION

    async def _async_update_ha_state(self, *args, **kwargs):
        await self.async_update_ha_state(self, *args, **kwargs)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.sensor.presence
