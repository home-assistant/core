"""
Obtain and set state of a Benq projector over telnet-to-serial gateway.
"""
import logging
import threading

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    STATE_ON, STATE_OFF, CONF_NAME, CONF_HOST)
import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import PlatformNotReady

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Benq Projector'
DEFAULT_TIMEOUT = None
DEFAULT_WRITE_TIMEOUT = None

LAMP_MODE = 'Lamp Mode'
ICON = 'mdi:projector'
INPUT_SOURCE = 'Input Source'
POWER = 'Power'
LAMP_HOURS = 'Lamp Hours'
MODEL = 'Model'

# Commands known to the projector
CMD_DICT = {
    POWER: '*pow=?#',
    LAMP_HOURS: '*ltim=?#',
    INPUT_SOURCE: '*sour=?#',
    LAMP_MODE: '*lampm=?#',
    MODEL: '*modelname=?#',
    STATE_ON: '*pow=on#',
    STATE_OFF: '*pow=off#',
}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Connect with telnet host and return Benq Projector."""
    import telnetlib

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    telnet = telnetlib.Telnet()
    try:
        telnet.open(host, timeout=5)
    except IOError as err:
        _LOGGER.error(err)
        raise PlatformNotReady
    finally:
        telnet.close()

    add_entities([BenqSwitch(telnet, host, name)], True)


class BenqSwitch(SwitchDevice):
    """Representation of a Benq Projector as a switch."""

    def __init__(self, telnet, host, name, **kwargs):
        """Init of the Benq projector."""
        self.telnet = telnet
        self._host = host
        self._name = name
        self._unique_id = host
        self._state = None
        self._available = False
        self._icon = ICON
        self._block = False
        self._lock = threading.Lock()
        self._attributes = {
            LAMP_HOURS: None,
            INPUT_SOURCE: None,
            LAMP_MODE: None,
            MODEL: None
        }

    def _handshake(self):
        """Initialization of communication with projector"""
        self.telnet.write(b'\r')
        answer = self.telnet.read_until(b">", timeout=1)
        return answer == b'>'

    def _write_read(self, msg):
        """Write to the projector and read the return."""
        for _ in range(1, 5):
            ready = self._handshake()
            if ready:
                break

        if ready:
            msg = msg.encode('utf-8')
            self.telnet.write(msg)

            expect = msg+b'\r\n'

            if self.telnet.read_until(expect, timeout=1) == expect:
                return self.telnet.read_until(b"#", timeout=1).decode('utf-8')

        return None

    def _write_read_format(self, msg):
        """Write msg, obtain answer and format output."""
        cmd = msg + '\r'

        _LOGGER.debug("Command send: %s", cmd)
        awns = self._write_read(cmd)

        _LOGGER.debug("Answer received: %s", awns)

        return awns

    def _open(self):
        self.telnet.open(self._host, timeout=5)

    def _close(self):
        self.telnet.close()

    def _update_state(self, awns):
        if awns == '*POW=ON#':
            self._state = True
            self._available = True
            self._block = False
        elif awns == '*POW=OFF#':
            self._state = False
            self._available = True
            self._block = False
        elif awns == '*Block item#':
            self._block = True
        else:
            self._available = False

    @property
    def available(self):
        """Return if projector is available."""
        return self._available

    @property
    def name(self):
        """Return name of the projector."""
        return self._name

    @property
    def unique_id(self):
        """Return an unique identifier for this entity."""
        return self._unique_id

    @property
    def icon(self):
        """Return an unique identifier for this entity."""
        return self._icon

    @property
    def is_on(self):
        """Return if the projector is turned on."""
        return self._state

    @property
    def state_attributes(self):
        """Return state attributes."""
        return self._attributes

    def update(self):
        """Get the latest state from the projector."""
        with self._lock:

            self._open()
            msg = CMD_DICT[POWER]
            awns = self._write_read_format(msg)

            self._update_state(awns)

            if self._state and not self._block:
                for key in self._attributes:
                    msg = CMD_DICT.get(key, None)
                    if msg:
                        awns = self._write_read_format(msg).split("=")[1]
                        self._attributes[key] = awns.split("#")[0]

            self._close()

    def turn_on(self, **kwargs):
        """Turn the projector on."""
        with self._lock:
            self._open()
            self._update_state(self._write_read_format(CMD_DICT[STATE_ON]))
            self._close()

        self.schedule_update_ha_state(True)

    def turn_off(self, **kwargs):
        """Turn the projector off."""
        with self._lock:
            self._open()
            self._update_state(self._write_read_format(CMD_DICT[STATE_OFF]))
            self._close()

        self.schedule_update_ha_state(True)
