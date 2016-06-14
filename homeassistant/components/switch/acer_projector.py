"""
Use serial protocol of acer projector to obtain state of the projector.

This component allows to control almost all projectors from acer using
their RS232 serial communication protocol.
"""

import logging
import re

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (STATE_ON, STATE_OFF, STATE_UNKNOWN,
                                 CONF_NAME, CONF_FILENAME)

LAMP_HOURS = 'Lamp Hours'
INPUT_SOURCE = 'Input Source'
ECO_MODE = 'ECO Mode'
MODEL = 'Model'
LAMP = 'Lamp'

# Commands known to the projector
CMD_DICT = {LAMP: '* 0 Lamp ?\r',
            LAMP_HOURS: '* 0 Lamp\r',
            INPUT_SOURCE: '* 0 Src ?\r',
            ECO_MODE: '* 0 IR 052\r',
            MODEL: '* 0 IR 035\r',
            STATE_ON: '* 0 IR 001\r',
            STATE_OFF: '* 0 IR 002\r'}

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['pyserial<=3.0']

ICON = 'mdi:projector'


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Connect with serial port and return Acer Projector."""
    serial_port = config.get(CONF_FILENAME, None)
    name = config.get(CONF_NAME, 'Projector')
    timeout = config.get('timeout', 1)
    write_timeout = config.get('write_timeout', 1)

    if not serial_port:
        _LOGGER.error('Missing path of serial device')
        return

    devices = []
    devices.append(AcerSwitch(serial_port, name, timeout, write_timeout))
    add_devices_callback(devices)


class AcerSwitch(SwitchDevice):
    """Represents an Acer Projector as an switch."""

    def __init__(self, serial_port, name='Projector',
                 timeout=1, write_timeout=1, **kwargs):
        """Init of the Acer projector."""
        import serial
        self.ser = serial.Serial(port=serial_port, timeout=timeout,
                                 write_timeout=write_timeout, **kwargs)
        self._serial_port = serial_port
        self._name = name
        self._state = STATE_UNKNOWN
        self._attributes = {
            LAMP_HOURS: STATE_UNKNOWN,
            INPUT_SOURCE: STATE_UNKNOWN,
            ECO_MODE: STATE_UNKNOWN,
        }
        self.update()

    def _write_read(self, msg):
        """Write to the projector and read the return."""
        import serial
        ret = ""
        # Sometimes the projector won't answer for no reason,
        # or the projector was disconnected during runtime.
        # Thisway the projector can be reconnected and will still
        # work
        try:
            if not self.ser.is_open:
                self.ser.open()
            msg = msg.encode('utf-8')
            self.ser.write(msg)
            # size is an experience value there is no real limit.
            # AFAIK there is no limit and no end character so
            # we will usually need to wait for timeout
            ret = self.ser.read_until(size=20).decode('utf-8')
        except serial.SerialException:
            _LOGGER.error('Problem comunicating with %s', self._serial_port)
        self.ser.close()
        return ret

    def _write_read_format(self, msg):
        """Write msg, obtain awnser and format output."""
        # awnsers are formated as ***\rawnser\r***
        awns = self._write_read(msg)
        match = re.search(r'\r(.+)\r', awns)
        if match:
            return match.group(1)
        return STATE_UNKNOWN

    @property
    def name(self):
        """Return name of the projector."""
        return self._name

    @property
    def state(self):
        """Return the current state of the projector."""
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
            self._state = STATE_ON
        elif awns == 'Lamp 0':
            self._state = STATE_OFF
        else:
            self._state = STATE_UNKNOWN

        for key in self._attributes.keys():
            msg = CMD_DICT.get(key, None)
            if msg:
                awns = self._write_read_format(msg)
                self._attributes[key] = awns

    def turn_on(self):
        """Turn the projector on."""
        msg = CMD_DICT[STATE_ON]
        self._write_read(msg)
        self._state = STATE_ON

    def turn_off(self):
        """Turn the projector off."""
        msg = CMD_DICT[STATE_OFF]
        self._write_read(msg)
        self._state = STATE_OFF
