"""
Use serial protocol of Acer projector to obtain state of the projector.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/switch.acer_projector/
"""
import logging
import re

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_UNKNOWN, CONF_NAME, CONF_FILENAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyserial==3.1.1']

_LOGGER = logging.getLogger(__name__)

CONF_TIMEOUT = 'timeout'
CONF_WRITE_TIMEOUT = 'write_timeout'

DEFAULT_NAME = 'Acer Projector'
DEFAULT_TIMEOUT = 1
DEFAULT_WRITE_TIMEOUT = 1

ECO_MODE = 'ECO Mode'

ICON = 'mdi:projector'

INPUT_SOURCE = 'Input Source'

LAMP = 'Lamp'
LAMP_HOURS = 'Lamp Hours'

MODEL = 'Model'

# Commands known to the projector
CMD_DICT = {
    LAMP: '* 0 Lamp ?\r',
    LAMP_HOURS: '* 0 Lamp\r',
    INPUT_SOURCE: '* 0 Src ?\r',
    ECO_MODE: '* 0 IR 052\r',
    MODEL: '* 0 IR 035\r',
    STATE_ON: '* 0 IR 001\r',
    STATE_OFF: '* 0 IR 002\r',
}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_FILENAME): cv.isdevice,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Optional(CONF_WRITE_TIMEOUT, default=DEFAULT_WRITE_TIMEOUT):
        cv.positive_int,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Connect with serial port and return Acer Projector."""
    serial_port = config.get(CONF_FILENAME)
    name = config.get(CONF_NAME)
    timeout = config.get(CONF_TIMEOUT)
    write_timeout = config.get(CONF_WRITE_TIMEOUT)

    add_entities([AcerSwitch(serial_port, name, timeout, write_timeout)], True)


class AcerSwitch(SwitchDevice):
    """Represents an Acer Projector as a switch."""

    def __init__(self, serial_port, name, timeout, write_timeout, **kwargs):
        """Init of the Acer projector."""
        import serial
        self.ser = serial.Serial(
            port=serial_port, timeout=timeout, write_timeout=write_timeout,
            **kwargs)
        self._serial_port = serial_port
        self._name = name
        self._state = False
        self._available = False
        self._attributes = {
            LAMP_HOURS: STATE_UNKNOWN,
            INPUT_SOURCE: STATE_UNKNOWN,
            ECO_MODE: STATE_UNKNOWN,
        }

    def _write_read(self, msg):
        """Write to the projector and read the return."""
        import serial
        ret = ""
        # Sometimes the projector won't answer for no reason or the projector
        # was disconnected during runtime.
        # This way the projector can be reconnected and will still work
        try:
            if not self.ser.is_open:
                self.ser.open()
            msg = msg.encode('utf-8')
            self.ser.write(msg)
            # Size is an experience value there is no real limit.
            # AFAIK there is no limit and no end character so we will usually
            # need to wait for timeout
            ret = self.ser.read_until(size=20).decode('utf-8')
        except serial.SerialException:
            _LOGGER.error('Problem communicating with %s', self._serial_port)
        self.ser.close()
        return ret

    def _write_read_format(self, msg):
        """Write msg, obtain answer and format output."""
        # answers are formatted as ***\answer\r***
        awns = self._write_read(msg)
        match = re.search(r'\r(.+)\r', awns)
        if match:
            return match.group(1)
        return STATE_UNKNOWN

    @property
    def available(self):
        """Return if projector is available."""
        return self._available

    @property
    def name(self):
        """Return name of the projector."""
        return self._name

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
        msg = CMD_DICT[LAMP]
        awns = self._write_read_format(msg)
        if awns == 'Lamp 1':
            self._state = True
            self._available = True
        elif awns == 'Lamp 0':
            self._state = False
            self._available = True
        else:
            self._available = False

        for key in self._attributes:
            msg = CMD_DICT.get(key, None)
            if msg:
                awns = self._write_read_format(msg)
                self._attributes[key] = awns

    def turn_on(self, **kwargs):
        """Turn the projector on."""
        msg = CMD_DICT[STATE_ON]
        self._write_read(msg)
        self._state = STATE_ON

    def turn_off(self, **kwargs):
        """Turn the projector off."""
        msg = CMD_DICT[STATE_OFF]
        self._write_read(msg)
        self._state = STATE_OFF
