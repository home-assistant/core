"""
Allows to configure a switch using RPi GPIO Servos.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.rpi_gpio/
"""
import logging

import voluptuous as vol
import homeassistant.components.rpi_gpio as GPIO
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['rpi_gpio']

CONF_PORTS = 'ports'
CONF_INACTIVE_POSTION = "default_position"
CONF_POSITION_ON = "position_on"
CONF_POSITION_OFF = "position_off"
CONF_POSITION_DURATION = "enabled_duration"
DEFAULT_INACTIVE_POSITION = 90
DEFAULT_POSITION_ON = 180
DEFAULT_POSITION_OFF = 0
DEFAULT_POSITION_DURATION = 1

_SWITCHES_SCHEMA = vol.Schema({
    cv.positive_int: cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PORTS): _SWITCHES_SCHEMA,
    vol.Optional(CONF_INACTIVE_POSTION,
                 default=DEFAULT_INACTIVE_POSITION): cv.positive_int,
    vol.Optional(CONF_POSITION_ON,
                 default=DEFAULT_POSITION_ON): cv.positive_int,
    vol.Optional(CONF_POSITION_OFF,
                 default=DEFAULT_POSITION_OFF): cv.positive_int,
    vol.Optional(CONF_POSITION_DURATION,
                 default=DEFAULT_POSITION_DURATION): cv.positive_int,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Raspberry PI GPIO servo devices."""
    inactive_position = config.get(CONF_INACTIVE_POSTION)
    position_on = config.get(CONF_POSITION_ON)
    position_off = config.get(CONF_POSITION_OFF)
    enabled_duration = config.get(CONF_POSITION_DURATION)
    switches = []
    ports = config.get(CONF_PORTS)
    for port, name in ports.items():
        switches.append(RPiGPIOServo(name, port, inactive_position,
                                     position_on, position_off,
                                     enabled_duration))
    add_devices(switches)


class RPiGPIOServo(ToggleEntity):
    """Representation of a  Raspberry Pi GPIO Servo."""

    def __init__(self, name, port, inactive_position, position_on,
                 position_off, enabled_duration):
        """Initialize the servo."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._port = port
        self._state = False
        self._inactive_position = inactive_position
        self._position_on = position_on
        self._position_off = position_off
        self._enabled_duration = enabled_duration
        GPIO.setup_output(port)

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        duty = get_duty(self._position_on)
        self._run_with_duty(duty)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        duty = get_duty(self._position_off)
        self._run_with_duty(duty)
        self._state = False
        self.schedule_update_ha_state()

    def _run_with_duty(self, duty):
        """Turn the servo to the given duty.

         Also turns it back to inactive unless duration is 0.
         """
        if self._enabled_duration == 0:
            GPIO.run_pwm(self._port, 50, duty, 2)
        else:
            GPIO.run_pwm(self._port, 50, duty, self._enabled_duration)
            duty = get_duty(self._inactive_position)
            GPIO.run_pwm(self._port, 50, duty, self._enabled_duration)


def get_duty(degrees):
    """Calculate the duty cycle given a number of degrees."""
    return float(degrees) / 18.0 + 2.5
