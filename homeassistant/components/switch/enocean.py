"""
Support for EnOcean switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.enocean/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_ID, CONF_COMMAND, CONF_CUSTOMIZE)
from homeassistant.components import enocean
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'EnOcean Switch'
DEPENDENCIES = ['enocean']
# New parameters for Nodon NOD_SIN-2-2-01 can work
DEFAULT_COMMAND = [0x00, 0x00, 0x00, 0x00, 0x00]
DEFAULT_CUSTOMIZE = [0x0]


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    # New parameters for Nodon NOD_SIN-2-2-01 can work
    vol.Optional(CONF_COMMAND, default=DEFAULT_COMMAND): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Optional(CONF_CUSTOMIZE, default=DEFAULT_CUSTOMIZE): vol.All(cv.ensure_list, [vol.Coerce(int)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the EnOcean switch platform."""
    dev_id = config.get(CONF_ID)
    devname = config.get(CONF_NAME)
    # New parameters for Nodon NOD_SIN-2-2-01 can work
    command = config.get(CONF_COMMAND)
    entity = config.get(CONF_CUSTOMIZE)
    add_devices([EnOceanSwitch(dev_id, devname, command, entity)])


class EnOceanSwitch(enocean.EnOceanDevice, ToggleEntity):
    """Representation of an EnOcean switch device."""

    def __init__(self, dev_id, devname, command, entity):
        """Initialize the EnOcean switch device."""
        enocean.EnOceanDevice.__init__(self)
        self.dev_id = dev_id
        self._devname = devname
        # New parameters for Nodon NOD_SIN-2-2-01 can work       
        self.dev_channel = command
        self.dev_entity = entity
        
        self._light = None
        self._on_state = False
        self._on_state2 = False
        self.stype = "switch"

    @property
    def is_on(self):
        """Return whether the switch is on or off."""
        return self._on_state

    @property
    def name(self):
        """Return the device name."""
        return self._devname

    def turn_on(self, **kwargs):
        """Turn on the switch."""
        optional = [0x03, ]
        optional.extend(self.dev_id)
        optional.extend([0xff, 0x00])
        
         # Customize Data for Nodon NOD_SIN-2-2-01 can work
        data 	= [0xD2, 0x01, ]
        data.extend(self.dev_entity) 
        data.extend([0x64, ]) 
        data.extend(self.dev_channel) 
        self.send_command(data=data, optional=optional, packet_type=0x01)
        self._on_state = True

    def turn_off(self, **kwargs):
        """Turn off the switch."""
        optional = [0x03, ]
        optional.extend(self.dev_id)
        optional.extend([0xff, 0x00])
        # Customize Data for Nodon NOD_SIN-2-2-01 can work
        data 	= [0xD2, 0x01, ]
        data.extend(self.dev_entity) 
        data.extend([0x00, ]) 
        data.extend(self.dev_channel) 

        self.send_command(data=data, optional=optional, packet_type=0x01)
        self._on_state = False

    def value_changed(self, val):
        """Update the internal state of the switch."""
        self._on_state = val
        self.schedule_update_ha_state()
