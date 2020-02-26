"""Support for EnOcean binary sensors."""
import logging

import voluptuous as vol

from homeassistant.components import enocean
from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    BinarySensorDevice,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ID, CONF_NAME
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_TYPE = "type"

DEFAULT_NAME = "EnOcean binary sensor"
DEPENDENCIES = ["enocean"]
EVENT_BUTTON_PRESSED = "button_pressed"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_TYPE, default=2): cv.positive_int,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Binary Sensor platform for EnOcean."""
    dev_id = config.get(CONF_ID)
    dev_name = config.get(CONF_NAME)
    device_class = config.get(CONF_DEVICE_CLASS)
    device_type = config.get(CONF_TYPE)

    add_entities([EnOceanBinarySensor(dev_id, dev_name, device_class, device_type)])


class EnOceanBinarySensor(enocean.EnOceanDevice, BinarySensorDevice):
    """Representation of EnOcean binary sensors such as wall switches.
    Supported EEPs (EnOcean Equipment Profiles):
    - F6-02-01 (Light and Blind Control - Application Style 2)
    - F6-02-02 (Light and Blind Control - Application Style 1)
    """

    def __init__(self, dev_id, dev_name, device_class, device_type):
        """Initialize the EnOcean binary sensor."""
        super().__init__(dev_id, dev_name)
        self._device_class = device_class
        self._device_type = device_type
        self.which = -1
        self.onoff = -1

    @property
    def name(self):
        """Return the default name for the binary sensor."""
        return self.dev_name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def device_type(self):
        """Return the type of this sensor."""
        return self._device_type

    def value_changed(self, packet):
        """Fire an event with the data that have changed.
        This method is called when there is an incoming packet associated
        with this platform.
        Example packet data:
        - 2nd button pressed
            ['0xf6', '0x10', '0x00', '0x2d', '0xcf', '0x45', '0x30']
        - button released
            ['0xf6', '0x00', '0x00', '0x2d', '0xcf', '0x45', '0x20']
        """

        if packet.data[0] == 0xf6:
          # Energy Bow
          pushed = None
          pressed = None
          first_action = None
          second_action = None
          second_action_valid = None

          
          if self._device_type == 2:
            packet.parse_eep(0x02, 0x02)
            pressed = packet.parsed['EB']['raw_value']
            first_action = packet.parsed['R1']['raw_value']
            second_action = packet.parsed['R2']['raw_value']
            second_action_valid = packet.parsed['SA']['raw_value']

          if packet.data[6] == 0x30:
              pushed = 1
          elif packet.data[6] == 0x20:
              pushed = 0

          self.schedule_update_ha_state()

          action = packet.data[1]
          if action == 0x70:
              self.which = 0
              self.onoff = 0
          elif action == 0x50:
              self.which = 0
              self.onoff = 1
          elif action == 0x30:
              self.which = 1
              self.onoff = 0
          elif action == 0x10:
              self.which = 1
              self.onoff = 1
          elif action == 0x37:
              self.which = 10
              self.onoff = 0
          elif action == 0x15:
              self.which = 10
              self.onoff = 1

          self.hass.bus.fire(
              EVENT_BUTTON_PRESSED,
              {
                  "id": self.dev_id,
                  "pushed": pushed,
                  "which": self.which,
                  "onoff": self.onoff,
                  "pressed": pressed,
                  "first_action": first_action,
                  "second_action": second_action,
                  "second_action_valid": second_action_valid,
              }
          )
