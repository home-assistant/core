"""Use serial protocol of BenQ projector to obtain state of the projector."""
# Forked on top of the Acer projector integration! https://github.com/home-assistant/core/tree/dev/homeassistant/components/acer_projector
# Credits = TrianguloY, CloudBurst, Hikaru, YayMuffins
import logging
import re

import serial
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import (
    CONF_FILENAME,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_BAUDRATE = "baudrate"
CONF_TIMEOUT = "timeout"
CONF_WRITE_TIMEOUT = "write_timeout"

DEFAULT_NAME = "BenQ Projector"
DEFAULT_TIMEOUT = 4
DEFAULT_WRITE_TIMEOUT = 4

LAMP_MODE = "Lamp Mode"

ICON = "mdi:projector"

INPUT_SOURCE = "Input Source"

LAMP = "Lamp"
LAMP_HOURS = "Lamp Hours"

MODEL = "Model"

# Commands known to the projector
#    STATE_OFF: "* 0 IR 002\r",
CMD_DICT = {
    LAMP: "\r*pow=?#\r",
    LAMP_HOURS: "\r*ltim=?#\r",
    INPUT_SOURCE: "\r*sour=?#\r",
    LAMP_MODE: "\r*lampm=?#\r",
    MODEL: "\r*modelname=?#\r",
    STATE_ON: "\r*pow=on#\r",
    STATE_OFF: "\r*pow=off#\r",
}

DEFAULT_BAUDRATE = 115200

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FILENAME): cv.isdevice,
        vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(
            CONF_WRITE_TIMEOUT, default=DEFAULT_WRITE_TIMEOUT
        ): cv.positive_int,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Connect with serial port and return BenQ Projector."""
    serial_port = config[CONF_FILENAME]
    baudrate = config[CONF_BAUDRATE]
    name = config[CONF_NAME]
    timeout = config[CONF_TIMEOUT]
    write_timeout = config[CONF_WRITE_TIMEOUT]

    add_entities([BenQSwitch(serial_port, baudrate, name, timeout, write_timeout)], True)


class BenQSwitch(SwitchEntity):
    """Represents an BenQ Projector as a switch."""

    def __init__(self, serial_port, baudrate, name, timeout, write_timeout, **kwargs):
        """Init of the BenQ projector."""

        self.ser = serial.Serial(
            port=serial_port, baudrate=baudrate, timeout=timeout, write_timeout=write_timeout, **kwargs
        )
        self._serial_port = serial_port
        self._baudrate = baudrate
        self._name = name
        self._state = False
        self._available = False
        self._attributes = {
            LAMP_HOURS: STATE_UNKNOWN,
            INPUT_SOURCE: STATE_UNKNOWN,
            LAMP_MODE: STATE_UNKNOWN,
        }

    def _write_read(self, msg):
        """Write to the projector and read the return."""

        ret = ""
        # Sometimes the projector won't answer for no reason or the projector
        # was disconnected during runtime.
        # This way the projector can be reconnected and will still work
        try:
            if not self.ser.is_open:
                self.ser.open()
            msg = msg.encode("ascii")
            self.ser.reset_input_buffer()
            self.ser.write(msg)
            # Size is an experience value there is no real limit.
            # AFAIK there is no limit and no end character so we will usually
            # need to wait for timeout
            self.ser.read_until(size=20)
            ret = self.ser.read_until(size=20).decode("ascii")
            #ret=self.ser.read(999).decode("ascii")


        except serial.SerialException:
            _LOGGER.error("Problem communicating with %s", self._serial_port)
        self.ser.close()
        return ret

    def _write_read_format(self, msg):
        """Write msg, obtain answer and format output."""
        # answers are formatted as ***\answer\r***
        awns = self._write_read(msg)
        _LOGGER.error("awns IN is: %s", repr(awns))
        match = re.search(r"=(.+)#", awns)
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
        _LOGGER.error("awns OUT is: %s", repr(awns))
        if awns == "ON":
            self._state = True
            self._available = True
        elif awns == "OFF":
            self._state = False
            self._available = True
        else:
            self._available = False

        for key in self._attributes:
            msg = CMD_DICT.get(key)
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