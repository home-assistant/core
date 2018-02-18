"""
Support for MAX! Eco Switches through a CUL stick.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.maxcul/
"""
import logging
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import dispatcher_connect
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_ID
from homeassistant.components.sensor import PLATFORM_SCHEMA

from homeassistant.components.maxcul import (
    DATA_MAXCUL,
    SIGNAL_PUSH_BUTTON_UPDATE
)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['maxcul']

CONF_ECO_SWITCHES = 'eco_switches'

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_ID): cv.positive_int,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ECO_SWITCHES): vol.Schema({
        cv.string: DEVICE_SCHEMA
    })
})

STATE_AUTO = 'auto'
STATE_ECO = 'eco'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the maxcul sensor platform."""
    devices = [
        MaxEcoSwitch(
            hass,
            device[CONF_ID],
            name
        )
        for name, device
        in config[CONF_ECO_SWITCHES].items()
    ]
    add_devices(devices)


class MaxEcoSwitch(Entity):
    """Representation of a MAX! Eco Switch."""

    def __init__(self, hass, device_id, name):
        """Initialize a new MAX! Eco Switch."""
        from maxcul import (
            ATTR_DEVICE_ID,
            ATTR_STATE
        )
        self._device_id = device_id
        self._name = name
        self._is_on = None
        self._maxcul_handle = hass[DATA_MAXCUL]

        self._maxcul_handle.add_paired_device(self._device_id)

        @callback
        def update(payload):
            """Handle eco switch updates."""
            if self._device_id != payload.get(ATTR_DEVICE_ID):
                return
            self._is_on = payload.get(ATTR_STATE)

            self.async_schedule_update_ha_state()

        dispatcher_connect(hass, SIGNAL_PUSH_BUTTON_UPDATE, update)

        self._maxcul_handle.wakeup(self._device_id)

    @property
    def should_poll(self):
        """Return whether or not this sensor need to be polled."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return STATE_ECO if self._is_on else STATE_AUTO
