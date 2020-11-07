"""Support for controlling a Raspberry Pi light."""

import time

import voluptuous as vol

from RPi import GPIO  # pylint: disable=import-error
from homeassistant.components import rpi_gpio
from homeassistant.components.light import PLATFORM_SCHEMA, LightEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import setup_reload_service
import uuid
import logging
from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONF_LIGHT = "lights"
CONF_RELAY_PIN = "relay_pin"
CONF_LIGHT_BUTTON_PIN = "light_button_pin"
CONF_LIGHT_BUTTON_PULL_MODE = "light_button_pull_mode"
CONF_INVERT_LIGHT_BUTTON = "invert_light_button"
CONF_INVERT_RELAY = "invert_relay"
CONF_LIGHT_BUTTON_BOUNCETIME_MILLIS = "light_button_bouncetime_millis"
CONF_LIGHT_BUTTON_DOUBLE_CHECK_TIME_MILLIS = "light_button_double_check_time_millis"
DEFAULT_LIGHT_BUTTON_PULL_MODE = "UP"
DEFAULT_INVERT_LIGHT_BUTTON = False
DEFAULT_INVERT_RELAY = False
DEFAULT_LIGHT_BUTTON_BOUNCETIME_MILLIS=100
DEFAULT_LIGHT_DOUBLE_CHECK_TIME_MILLIS=25

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        CONF_LIGHT:[
            vol.Schema(
                {
                    vol.Required(CONF_NAME): cv.string,
                    vol.Required(CONF_RELAY_PIN): cv.positive_int,
                    vol.Required(CONF_LIGHT_BUTTON_PIN): cv.positive_int,
                }
            )
        ],
        vol.Optional(CONF_LIGHT_BUTTON_PULL_MODE, default=DEFAULT_LIGHT_BUTTON_PULL_MODE): cv.string,
        vol.Optional(CONF_LIGHT_BUTTON_BOUNCETIME_MILLIS, default=DEFAULT_LIGHT_BUTTON_BOUNCETIME_MILLIS): cv.positive_int,
        vol.Optional(CONF_LIGHT_BUTTON_DOUBLE_CHECK_TIME_MILLIS, default=DEFAULT_LIGHT_DOUBLE_CHECK_TIME_MILLIS): cv.positive_int,
        vol.Optional(CONF_INVERT_LIGHT_BUTTON, default=DEFAULT_INVERT_LIGHT_BUTTON): cv.boolean,
        vol.Optional(CONF_INVERT_RELAY, default=DEFAULT_INVERT_RELAY): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the RPi light platform."""

    setup_reload_service(hass, DOMAIN, PLATFORMS)

    light_button_pull_mode = config.get(CONF_LIGHT_BUTTON_PULL_MODE)
    invert_light_button = config.get(CONF_INVERT_LIGHT_BUTTON)
    invert_relay = config.get(CONF_INVERT_RELAY)
    light_button_bouncetime_millis = config.get(CONF_LIGHT_BUTTON_BOUNCETIME_MILLIS)
    light_button_double_check_time_millis = config.get(CONF_LIGHT_BUTTON_DOUBLE_CHECK_TIME_MILLIS)
    lights = []
    lights_conf = config.get(CONF_LIGHT)

    for light in lights_conf:
        lights.append(
            RPiGPIOLight(
                light[CONF_NAME],
                light[CONF_RELAY_PIN],
                light[CONF_LIGHT_BUTTON_PIN],
                light_button_pull_mode,
                light_button_bouncetime_millis,
                light_button_double_check_time_millis,
                invert_light_button,
                invert_relay,
            )
        )
    add_entities(lights)


class RPiGPIOLight(LightEntity):
    """Representation of a Raspberry GPIO light."""

    TIMERS = {}

    def __init__(
        self,
        name,
        relay_pin,
        light_button_pin,
        light_button_pull_mode,
        light_button_bouncetime_millis,
        light_button_double_check_time_millis,
        invert_light_button,
        invert_relay,
    ):
        """Initialize the light."""
        self._name = name
        self._state = False
        self._relay_pin = relay_pin
        self._light_button_pin = light_button_pin
        self._light_button_pull_mode = light_button_pull_mode
        self._light_button_bouncetime_millis=light_button_bouncetime_millis
        self._light_button_double_check_time_millis = light_button_double_check_time_millis
        self._invert_light_button = invert_light_button
        self._invert_relay = invert_relay
        rpi_gpio.setup_output(self._relay_pin)
        rpi_gpio.setup_input(self._light_button_pin, self._light_button_pull_mode)
        rpi_gpio.write_output(self._relay_pin, 1 if self._invert_relay else 0)

        def toggle_light_switch(port):
            time.sleep(self._light_button_double_check_time_millis / 2000)
            if rpi_gpio.read_input(self._light_button_pin)!=self._invert_light_button:
                time.sleep(self._light_button_double_check_time_millis/2000) #double check to avoid electrical disturbance
                if rpi_gpio.read_input(self._light_button_pin) != self._invert_light_button:
                    self.toggle()


        if(self._invert_light_button):
            rpi_gpio.falling_edge_detect(self._light_button_pin, toggle_light_switch, self._light_button_bouncetime_millis)
        else:
            rpi_gpio.rising_edge_detect(self._light_button_pin, toggle_light_switch, self._light_button_bouncetime_millis)

    @property
    def name(self):
        """Return the name of the light if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    def turn_on(self, **kwargs):
        """turn_on the light and trigger the timer."""
        rpi_gpio.write_output(self._relay_pin, 0 if self._invert_relay else 1)
        self._state = True

    def turn_off(self,  **kwargs):
        """turn_off the light."""
        rpi_gpio.write_output(self._relay_pin, 1 if self._invert_relay else 0)
        self._state = False
