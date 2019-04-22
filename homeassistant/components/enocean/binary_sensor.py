"""Support for EnOcean binary sensors."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA, DEVICE_CLASSES_SCHEMA)
from homeassistant.components import enocean
from homeassistant.const import (
    CONF_NAME, CONF_ID, CONF_DEVICE_CLASS)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'EnOcean binary sensor'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Binary Sensor platform for EnOcean."""
    dev_id = config.get(CONF_ID)
    devname = config.get(CONF_NAME)
    device_class = config.get(CONF_DEVICE_CLASS)

    add_entities([EnOceanBinarySensor(dev_id, devname, device_class)])


class EnOceanBinarySensor(enocean.EnOceanDevice, BinarySensorDevice):
    """Representation of EnOcean binary sensors such as wall switches."""

    def __init__(self, dev_id, devname, device_class):
        """Initialize the EnOcean binary sensor."""
        enocean.EnOceanDevice.__init__(self)
        self.stype = 'listener'
        self.dev_id = dev_id
        self.which = -1
        self.onoff = -1
        self.devname = devname
        self._device_class = device_class

    @property
    def name(self):
        """Return the default name for the binary sensor."""
        return self.devname

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    def value_changed(self, value, value2):
        """Fire an event with the data that have changed.

        This method is called when there is an incoming packet associated
        with this platform.
        """
        self.schedule_update_ha_state()
        if value2 == 0x70:
            self.which = 0
            self.onoff = 0
        elif value2 == 0x50:
            self.which = 0
            self.onoff = 1
        elif value2 == 0x30:
            self.which = 1
            self.onoff = 0
        elif value2 == 0x10:
            self.which = 1
            self.onoff = 1
        elif value2 == 0x37:
            self.which = 10
            self.onoff = 0
        elif value2 == 0x15:
            self.which = 10
            self.onoff = 1
        self.hass.bus.fire('button_pressed', {'id': self.dev_id,
                                              'pushed': value,
                                              'which': self.which,
                                              'onoff': self.onoff})
