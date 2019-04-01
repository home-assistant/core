from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.hue.hue_sensor import (
    GenericZLLSensor, async_setup_entry as shared_async_setup_entry)


async def async_setup_entry(hass, config_entry, async_add_entities):
    await shared_async_setup_entry(
        hass, config_entry, async_add_entities, binary=True)


class HuePresence(GenericZLLSensor, BinarySensorDevice):
    """The presence sensor entity for a Hue motion sensor device."""

    device_class = 'presence'
    icon = 'mdi:run'

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.sensor.presence


class HueNotDarkness(GenericZLLSensor, BinarySensorDevice):
    """A binary light sensor entity for a Hue motion sensor device."""

    device_class = 'light'

    @property
    def is_on(self):
        """Return the state of the device."""
        return not self.sensor.dark

    @property
    def unique_id(self):
        """Return the ID of this Hue sensor."""
        return self.sensor.uniqueid + '-not-dark'

    @property
    def icon(self):
        """Return an icon representing the entity and its state."""
        return self.is_on and 'mdi:lightbulb-on' or 'mdi:lightbulb-off'

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = super().device_state_attributes
        attributes.update({
            "threshold_dark": self.sensor.tholddark,
            "threshold_offset": self.sensor.tholdoffset,
        })
        return attributes
