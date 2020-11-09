"""Support for controlling a Raspberry Pi light."""

import logging
import time

from homeassistant.components import rpi_gpio_light
from homeassistant.components.light import LightEntity
from homeassistant.const import CONF_NAME

from .const import (
    CONF_INVERT_LIGHT_BUTTON,
    CONF_INVERT_RELAY,
    CONF_LIGHT,
    CONF_LIGHT_BUTTON_BOUNCETIME_MILLIS,
    CONF_LIGHT_BUTTON_DOUBLE_CHECK_TIME_MILLIS,
    CONF_LIGHT_BUTTON_PIN,
    CONF_LIGHT_BUTTON_PULL_MODE,
    CONF_RELAY_PIN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the RPi light platform."""

    light_button_pull_mode = hass.data[DOMAIN][CONF_LIGHT_BUTTON_PULL_MODE]
    invert_light_button = hass.data[DOMAIN][CONF_INVERT_LIGHT_BUTTON]
    invert_relay = hass.data[DOMAIN][CONF_INVERT_RELAY]
    light_button_bouncetime_millis = hass.data[DOMAIN][
        CONF_LIGHT_BUTTON_BOUNCETIME_MILLIS
    ]
    light_button_double_check_time_millis = hass.data[DOMAIN][
        CONF_LIGHT_BUTTON_DOUBLE_CHECK_TIME_MILLIS
    ]
    lights = []

    for light in hass.data[DOMAIN][CONF_LIGHT]:
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
        self._light_button_bouncetime_millis = light_button_bouncetime_millis
        self._light_button_double_check_time_millis = (
            light_button_double_check_time_millis
        )
        self._invert_light_button = invert_light_button
        self._invert_relay = invert_relay
        rpi_gpio_light.setup_output(self._relay_pin)
        rpi_gpio_light.setup_input(self._light_button_pin, self._light_button_pull_mode)
        rpi_gpio_light.write_output(self._relay_pin, 1 if self._invert_relay else 0)

        def toggle_light_from_button(port):
            time.sleep(self._light_button_double_check_time_millis / 2000)
            if (
                rpi_gpio_light.read_input(self._light_button_pin)
                != self._invert_light_button
            ):
                time.sleep(
                    self._light_button_double_check_time_millis / 2000
                )  # double check to avoid electrical disturbance
                if (
                    rpi_gpio_light.read_input(self._light_button_pin)
                    != self._invert_light_button
                ):
                    self.toggle()

        if self._invert_light_button:
            rpi_gpio_light.falling_edge_detect(
                self._light_button_pin,
                toggle_light_from_button,
                self._light_button_bouncetime_millis,
            )
        else:
            rpi_gpio_light.rising_edge_detect(
                self._light_button_pin,
                toggle_light_from_button,
                self._light_button_bouncetime_millis,
            )

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
        rpi_gpio_light.write_output(self._relay_pin, 0 if self._invert_relay else 1)
        self._state = True

    def turn_off(self, **kwargs):
        """turn_off the light."""
        rpi_gpio_light.write_output(self._relay_pin, 1 if self._invert_relay else 0)
        self._state = False
