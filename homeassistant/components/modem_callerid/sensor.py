"""
A sensor to monitor incoming calls using a USB modem that supports caller ID.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.modem_callerid/
"""
import logging
import voluptuous as vol
from homeassistant.const import (STATE_IDLE,
                                 EVENT_HOMEASSISTANT_STOP,
                                 CONF_NAME,
                                 CONF_DEVICE)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['basicmodem==0.7']

_LOGGER = logging.getLogger(__name__)
DEFAULT_NAME = 'Modem CallerID'
ICON = 'mdi:phone-classic'
DEFAULT_DEVICE = '/dev/ttyACM0'

STATE_RING = 'ring'
STATE_CALLERID = 'callerid'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up modem caller ID sensor platform."""
    from basicmodem.basicmodem import BasicModem as bm
    name = config.get(CONF_NAME)
    port = config.get(CONF_DEVICE)

    modem = bm(port)
    if modem.state == modem.STATE_FAILED:
        _LOGGER.error('Unable to initialize modem.')
        return

    add_entities([ModemCalleridSensor(hass, name, port, modem)])


class ModemCalleridSensor(Entity):
    """Implementation of USB modem caller ID sensor."""

    def __init__(self, hass, name, port, modem):
        """Initialize the sensor."""
        self._attributes = {"cid_time": 0, "cid_number": '', "cid_name": ''}
        self._name = name
        self.port = port
        self.modem = modem
        self._state = STATE_IDLE
        modem.registercallback(self._incomingcallcallback)
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, self._stop_modem)

    def set_state(self, state):
        """Set the state."""
        self._state = state

    def set_attributes(self, attributes):
        """Set the state attributes."""
        self._attributes = attributes

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def _stop_modem(self, event):
        """HA is shutting down, close modem port."""
        if self.modem:
            self.modem.close()
            self.modem = None

    def _incomingcallcallback(self, newstate):
        """Handle new states."""
        if newstate == self.modem.STATE_RING:
            if self.state == self.modem.STATE_IDLE:
                att = {"cid_time": self.modem.get_cidtime,
                       "cid_number": '',
                       "cid_name": ''}
                self.set_attributes(att)
            self._state = STATE_RING
            self.schedule_update_ha_state()
        elif newstate == self.modem.STATE_CALLERID:
            att = {"cid_time": self.modem.get_cidtime,
                   "cid_number": self.modem.get_cidnumber,
                   "cid_name": self.modem.get_cidname}
            self.set_attributes(att)
            self._state = STATE_CALLERID
            self.schedule_update_ha_state()
        elif newstate == self.modem.STATE_IDLE:
            self._state = STATE_IDLE
            self.schedule_update_ha_state()
