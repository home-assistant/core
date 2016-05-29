"""
Support for EnOcean binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.enocean/
"""

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components import enocean
from homeassistant.const import CONF_NAME

DEPENDENCIES = ["enocean"]

CONF_ID = "id"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Binary Sensor platform fo EnOcean."""
    dev_id = config.get(CONF_ID, None)
    devname = config.get(CONF_NAME, "EnOcean binary sensor")
    add_devices([EnOceanBinarySensor(dev_id, devname)])


class EnOceanBinarySensor(enocean.EnOceanDevice, BinarySensorDevice):
    """Representation of EnOcean binary sensors such as wall switches."""

    def __init__(self, dev_id, devname):
        """Initialize the EnOcean binary sensor."""
        enocean.EnOceanDevice.__init__(self)
        self.stype = "listener"
        self.dev_id = dev_id
        self.which = -1
        self.onoff = -1
        self.devname = devname

    @property
    def name(self):
        """The default name for the binary sensor."""
        return self.devname

    def value_changed(self, value, value2):
        """Fire an event with the data that have changed.

        This method is called when there is an incoming packet associated
        with this platform.
        """
        self.update_ha_state()
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
        self.hass.bus.fire('button_pressed', {"id": self.dev_id,
                                              'pushed': value,
                                              'which': self.which,
                                              'onoff': self.onoff})
