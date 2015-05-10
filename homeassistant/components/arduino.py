"""
components.arduino
~~~~~~~~~~~~~~~~~~
Arduino component that connects to a directly attached Arduino board which
runs with the Firmata firmware.

Configuration:

To use the Arduino board you will need to add something like the following
to your config/configuration.yaml

arduino:
    port: /dev/ttyACM0

If you are using an original Arduino the port will be named ttyACM*. The exact
number can be determined with 'ls /dev/ttyACM*' or check your 'dmesg'/
'journalctl -f' output. Keep in mind that Arduino clones are often using a
different name for the port (e.g. '/dev/ttyUSB*').

A word of caution: The Arduino is not storing states. This means that with
every initializsation

TODO:
- Check Firmata version
- Check if communication with board is ready
- Close the connection to the board
- Add capability to use analog and digital pins as sensors
- Add PWM output feature
- I2C

"""
import logging

from homeassistant.helpers import validate_config
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import (STATE_ON, STATE_OFF, DEVICE_DEFAULT_NAME)


DOMAIN = "arduino"
DEPENDENCIES = []
BOARD = None

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """ Setup the Arduino component. """

    # pylint: disable=global-statement
    if not validate_config(config,
                           {DOMAIN: ['port']},
                           _LOGGER):
        return False

    try:
        from PyMata.pymata import PyMata

    except ImportError:
        _LOGGER.error("Error while importing dependency pyMata.")

        return False

    global BOARD
    BOARD = ArduinoBoard(config[DOMAIN]['port'])

    return True


class ArduinoBoard():
    """ Represents an Arduino board within Home Assistant. """

    def __init__(self, port):
        try:
            from PyMata.pymata import PyMata

        except ImportError:
            _LOGGER.error("Error while importing dependency pyMata.")

        self._port = port
        self._board = PyMata(self._port, verbose=False)

    def set_mode(self, pin, direction, mode):
        """ Sets the mode and the direction of a given pin. """
        if mode == 'analog' and direction == 'in':
            self._board.set_pin_mode(pin,
                                     self._board.INPUT,
                                     self._board.ANALOG)
            self._board.enable_analog_reporting(pin)
        elif mode == 'analog' and direction == 'out':
            self._board.set_pin_mode(pin,
                                     self._board.OUTPUT,
                                     self._board.ANALOG)
        elif mode == 'digital' and direction == 'in':
            self._board.set_pin_mode(pin,
                                     self._board.OUTPUT,
                                     self._board.DIGITAL)
            self._board.enable_digital_reporting(pin)
        elif mode == 'digital' and direction == 'out':
            self._board.set_pin_mode(pin,
                                     self._board.OUTPUT,
                                     self._board.DIGITAL)
        elif mode == 'pwm':
            self._board.set_pin_mode(pin,
                                     self._board.OUTPUT,
                                     self._board.PWM)

    def digital_out_high(self, pin):
        """ Sets a given digital pin to high. """
        self._board.digital_write(pin, 1)

    def digital_out_low(self, pin):
        """ Sets a given digital pin to low. """
        self._board.digital_write(pin, 0)

    def get_firmata(self):
        """ Return the version of the Firmata firmware. """
        return self._board.get_firmata_version()

    def disconnect(self):
        """ Disconnects the board and closes the serial connection. """
        self._board.close


class ArduinoDeviceABC(ToggleEntity):
    """ Abstract Class for an Arduino board within Home Assistant. """

    _states = []
    _domain = None
    _name = None

    def __init__(self, name, pin):
        # Setup properties
        self._pin = pin
        self._name = name  or DEVICE_DEFAULT_NAME
        self._state = STATE_OFF
        self._value = None

    @property
    def domain(self):
        """ Returns the domain of the entity. """
        return self._domain

    @property
    def is_on(self):
        """ Returns True if switch is on. """
        return self._state == STATE_ON

    @property
    def should_poll(self):
        """ Tells Home Assistant not to poll this entity. """
        return False

    @property
    def name(self):
        """ Returns the name of the pin. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device if any. """
        return self._state

    def on_update(self, event):
        """ Handles the update received event. """
        self.update_ha_state()

    def turn_on(self):
        """ Turns the pin to high/on. """
        if self.domain is not 'sensor':
            self._state = STATE_ON
            BOARD.set_mode(self._pin, 'out', 'digital')
            BOARD.digital_out_high(self._pin)
        else:
            _LOGGER.error('pyMata cannot turn on sensors.')

    def turn_off(self):
        """ Turns the pin to low/off. """
        if self.domain is not 'sensor':
            self._state = STATE_OFF
            BOARD.set_mode(self._pin, 'out', 'digital')
            BOARD.digital_out_low(self._pin)
        else:
            _LOGGER.error('pyMata cannot turn off sensors.')
