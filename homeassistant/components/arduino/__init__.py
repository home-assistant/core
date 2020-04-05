"""Support for Arduino boards running with the Firmata firmware."""
import logging

from PyMata.pymata import PyMata
import serial
import voluptuous as vol

from homeassistant.const import (
    CONF_PORT,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

BOARD = None

DOMAIN = "arduino"

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_PORT): cv.string})}, extra=vol.ALLOW_EXTRA
)


def setup(hass, config):
    """Set up the Arduino component."""

    port = config[DOMAIN][CONF_PORT]

    global BOARD  # pylint: disable=global-statement
    try:
        BOARD = ArduinoBoard(port)
    except (serial.serialutil.SerialException, FileNotFoundError):
        _LOGGER.error("Your port %s is not accessible", port)
        return False

    try:
        if BOARD.get_firmata()[1] <= 2:
            _LOGGER.error("The StandardFirmata sketch should be 2.2 or newer")
            return False
    except IndexError:
        _LOGGER.warning(
            "The version of the StandardFirmata sketch was not"
            "detected. This may lead to side effects"
        )

    def stop_arduino(event):
        """Stop the Arduino service."""
        BOARD.disconnect()

    def start_arduino(event):
        """Start the Arduino service."""
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_arduino)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_arduino)

    return True


class ArduinoBoard:
    """Representation of an Arduino board."""

    def __init__(self, port):
        """Initialize the board."""

        self._port = port
        self._board = PyMata(self._port, verbose=False)

    def set_mode(self, pin, direction, mode):
        """Set the mode and the direction of a given pin."""
        if mode == "analog" and direction == "in":
            self._board.set_pin_mode(pin, self._board.INPUT, self._board.ANALOG)
        elif mode == "analog" and direction == "out":
            self._board.set_pin_mode(pin, self._board.OUTPUT, self._board.ANALOG)
        elif mode == "digital" and direction == "in":
            self._board.set_pin_mode(pin, self._board.INPUT, self._board.DIGITAL)
        elif mode == "digital" and direction == "out":
            self._board.set_pin_mode(pin, self._board.OUTPUT, self._board.DIGITAL)
        elif mode == "pwm":
            self._board.set_pin_mode(pin, self._board.OUTPUT, self._board.PWM)

    def get_analog_inputs(self):
        """Get the values from the pins."""
        self._board.capability_query()
        return self._board.get_analog_response_table()

    def set_digital_out_high(self, pin):
        """Set a given digital pin to high."""
        self._board.digital_write(pin, 1)

    def set_digital_out_low(self, pin):
        """Set a given digital pin to low."""
        self._board.digital_write(pin, 0)

    def get_digital_in(self, pin):
        """Get the value from a given digital pin."""
        self._board.digital_read(pin)

    def get_analog_in(self, pin):
        """Get the value from a given analog pin."""
        self._board.analog_read(pin)

    def get_firmata(self):
        """Return the version of the Firmata firmware."""
        return self._board.get_firmata_version()

    def disconnect(self):
        """Disconnect the board and close the serial connection."""
        self._board.reset()
        self._board.close()
