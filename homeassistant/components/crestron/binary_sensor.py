"""Support for Crestron binary sensors."""
import voluptuous as vol

import logging

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorDevice
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from . import CRESTRON_CONTROLLER

CONF_DIGITAL_JOIN_IN_STATUS = "digital_join_in_status"

DEFAULT_NAME = "Crestron Binary Sensor"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_DIGITAL_JOIN_IN_STATUS): cv.positive_int,
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
    join_status = config[CONF_DIGITAL_JOIN_IN_STATUS]

    crestron = hass.data[CRESTRON_CONTROLLER]
    entity = CrestronBinarySensor(name= name, join_status= join_status, controller= crestron)
    async_add_entities([entity])


class CrestronBinarySensor(BinarySensorDevice):
    """Representation of a Crestron binary sensor."""

    def __init__(self, name, join_status, controller):
        """Initialize of Crestron binary sensor."""  
        self._name = name
        self._join_status = join_status
        self._controller = controller
        self._state = controller.get("d", join_status)
        

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""

        def after_update_callback(sigtype, join, state):
            """Call after device was updated."""
            self._state = state
            self.async_write_ha_state()

        self._controller.subscribe("d", self._join_status, after_update_callback)

    async def async_added_to_hass(self):
        """Store register state change callback."""
        self.async_register_callbacks()

    @property
    def name(self):
        """Return the name of the Crestron device."""
        return self._name

    @property
    def available(self):
        """Return True if entity is available."""
        return self._controller.connected

    @property
    def should_poll(self):
        """No polling needed within Crestron."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        attr["crestron_digital_in"] = self._join_status
        return attr

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

