"""
Support for EnOcean sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.enocean/
"""

from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.components import enocean

DEPENDENCIES = ["enocean"]

CONF_ID = "id"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup an EnOcean sensor device."""
    dev_id = config.get(CONF_ID, None)
    devname = config.get(CONF_NAME, None)
    add_devices([EnOceanSensor(dev_id, devname)])


class EnOceanSensor(enocean.EnOceanDevice, Entity):
    """Representation of an EnOcean sensor device such as a power meter."""

    def __init__(self, dev_id, devname):
        """Initialize the EnOcean sensor device."""
        enocean.EnOceanDevice.__init__(self)
        self.stype = "powersensor"
        self.power = None
        self.dev_id = dev_id
        self.which = -1
        self.onoff = -1
        self.devname = devname

    @property
    def name(self):
        """Return the name of the device."""
        return 'Power %s' % self.devname

    def value_changed(self, value):
        """Update the internal state of the device."""
        self.power = value
        self.update_ha_state()

    @property
    def state(self):
        """Return the state of the device."""
        return self.power

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "W"
