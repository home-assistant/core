"""Support for Crestron switches in DIN."""
import voluptuous as vol

import logging
import asyncio
import time

from homeassistant.components.switch import DOMAIN, PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import CONF_NAME, ATTR_ID
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import CRESTRON_CONTROLLER

CONF_DIGITAL_JOIN = "join"
CONF_DIGITAL_JOIN_IS_PULSED = "join_is_pulsed"
CONF_DIGITAL_JOIN_ONE_SHOT_TIME = "join_one_shot_time"

ATTR_ACTION = "action"

DEFAULT_NAME = "Crestron Switch"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_DIGITAL_JOIN): cv.positive_int,
        vol.Optional(CONF_DIGITAL_JOIN_IS_PULSED, default=False): cv.boolean,
        vol.Optional(CONF_DIGITAL_JOIN_ONE_SHOT_TIME, default=0): cv.positive_int,
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up binary sensor(s) for Crestron platform."""
    if config == {}:
        return
    async_add_entities_config(hass, config, async_add_entities)

@callback
def async_add_entities_config(hass, config, async_add_entities):
    """Set up binary sensor for Crestron platform configured within platform."""
    name = config[CONF_NAME]
    join = config[CONF_DIGITAL_JOIN]
    join_is_pulsed = config[CONF_DIGITAL_JOIN_IS_PULSED]
    crestron = hass.data[CRESTRON_CONTROLLER]
    entity = CrestronSwitch(name= name, join= join, join_is_pulsed=join_is_pulsed, controller= crestron)
    async_add_entities([entity])

_LOGGER = logging.getLogger(__name__)

class CrestronSwitch(SwitchDevice):
    """Representation of a Crestron Switch."""

    def __init__(self, name, join, join_is_pulsed, controller):
        """Initialize the switch."""
        self._join = join
        self._join_is_pulsed = join_is_pulsed
        self._name = name
        self._state = False
        self._event = "crestron_event"
        self._controller = controller
    
    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        if self._join_is_pulsed:
            self._controller.pulse(self._join)
            data = {ATTR_ID: self._join, ATTR_ACTION: 'pulsed'}
            self.hass.bus.fire(self._event, data)

        else:
            self._controller.set("d",self._join,1)
            self._state = True
            self.async_write_ha_state()
              

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""

        if self._join_is_pulsed:
            self._controller.pulse(self._join)
        else:
            self._controller.set("d",self._join,0)
            self._state = False
            self.async_write_ha_state()

    @property
    def name(self):
        """Return the name of the Crestron device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        attr["crestron_digital_out"] = self._join
        return attr
    
    @property
    def should_poll(self):
        """No polling needed within Crestron."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Call when forcing a refresh of the device."""
        pass

