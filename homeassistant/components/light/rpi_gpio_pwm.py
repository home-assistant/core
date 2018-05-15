"""
Support for LED lights that can be controlled using PWM.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.pwm/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_TYPE
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_HS_COLOR, ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR, SUPPORT_TRANSITION, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

REQUIREMENTS = ['pwmled==1.2.1']

_LOGGER = logging.getLogger(__name__)

CONF_LEDS = 'leds'
CONF_DRIVER = 'driver'
CONF_PINS = 'pins'
CONF_FREQUENCY = 'frequency'
CONF_ADDRESS = 'address'

CONF_DRIVER_GPIO = 'gpio'
CONF_DRIVER_PCA9685 = 'pca9685'
CONF_DRIVER_TYPES = [CONF_DRIVER_GPIO, CONF_DRIVER_PCA9685]

CONF_LED_TYPE_SIMPLE = 'simple'
CONF_LED_TYPE_RGB = 'rgb'
CONF_LED_TYPE_RGBW = 'rgbw'
CONF_LED_TYPES = [CONF_LED_TYPE_SIMPLE, CONF_LED_TYPE_RGB, CONF_LED_TYPE_RGBW]

DEFAULT_COLOR = [0, 0]

SUPPORT_SIMPLE_LED = (SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION)
SUPPORT_RGB_LED = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_TRANSITION)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_LEDS): vol.All(cv.ensure_list, [
        {
            vol.Required(CONF_NAME): cv.string,
            vol.Required(CONF_DRIVER): vol.In(CONF_DRIVER_TYPES),
            vol.Required(CONF_PINS): vol.All(cv.ensure_list,
                                             [cv.positive_int]),
            vol.Required(CONF_TYPE): vol.In(CONF_LED_TYPES),
            vol.Optional(CONF_FREQUENCY): cv.positive_int,
            vol.Optional(CONF_ADDRESS): cv.byte
        }
    ])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the PWM LED lights."""
    from pwmled.led import SimpleLed
    from pwmled.led.rgb import RgbLed
    from pwmled.led.rgbw import RgbwLed
    from pwmled.driver.gpio import GpioDriver
    from pwmled.driver.pca9685 import Pca9685Driver

    leds = []
    for led_conf in config[CONF_LEDS]:
        driver_type = led_conf[CONF_DRIVER]
        pins = led_conf[CONF_PINS]
        opt_args = {}
        if CONF_FREQUENCY in led_conf:
            opt_args['freq'] = led_conf[CONF_FREQUENCY]
        if driver_type == CONF_DRIVER_GPIO:
            driver = GpioDriver(pins, **opt_args)
        elif driver_type == CONF_DRIVER_PCA9685:
            if CONF_ADDRESS in led_conf:
                opt_args['address'] = led_conf[CONF_ADDRESS]
            driver = Pca9685Driver(pins, **opt_args)
        else:
            _LOGGER.error("Invalid driver type")
            return

        name = led_conf[CONF_NAME]
        led_type = led_conf[CONF_TYPE]
        if led_type == CONF_LED_TYPE_SIMPLE:
            led = PwmSimpleLed(SimpleLed(driver), name)
        elif led_type == CONF_LED_TYPE_RGB:
            led = PwmRgbLed(RgbLed(driver), name)
        elif led_type == CONF_LED_TYPE_RGBW:
            led = PwmRgbLed(RgbwLed(driver), name)
        else:
            _LOGGER.error("Invalid led type")
            return
        leds.append(led)

    add_devices(leds)


class PwmSimpleLed(Light):
    """Representation of a simple one-color PWM LED."""

    def __init__(self, led, name):
        """Initialize one-color PWM LED."""
        self._led = led
        self._name = name
        self._is_on = False
        self._brightness = 255

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the group."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._is_on

    @property
    def brightness(self):
        """Return the brightness property."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_SIMPLE_LED

    def turn_on(self, **kwargs):
        """Turn on a led."""
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_TRANSITION in kwargs:
            transition_time = kwargs[ATTR_TRANSITION]
            self._led.transition(
                transition_time,
                is_on=True,
                brightness=_from_hass_brightness(self._brightness))
        else:
            self._led.set(is_on=True,
                          brightness=_from_hass_brightness(self._brightness))

        self._is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn off a LED."""
        if self.is_on:
            if ATTR_TRANSITION in kwargs:
                transition_time = kwargs[ATTR_TRANSITION]
                self._led.transition(transition_time, is_on=False)
            else:
                self._led.off()

        self._is_on = False
        self.schedule_update_ha_state()


class PwmRgbLed(PwmSimpleLed):
    """Representation of a RGB(W) PWM LED."""

    def __init__(self, led, name):
        """Initialize a RGB(W) PWM LED."""
        super().__init__(led, name)
        self._color = DEFAULT_COLOR

    @property
    def hs_color(self):
        """Return the color property."""
        return self._color

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_RGB_LED

    def turn_on(self, **kwargs):
        """Turn on a LED."""
        if ATTR_HS_COLOR in kwargs:
            self._color = kwargs[ATTR_HS_COLOR]
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_TRANSITION in kwargs:
            transition_time = kwargs[ATTR_TRANSITION]
            self._led.transition(
                transition_time,
                is_on=True,
                brightness=_from_hass_brightness(self._brightness),
                color=_from_hass_color(self._color))
        else:
            self._led.set(is_on=True,
                          brightness=_from_hass_brightness(self._brightness),
                          color=_from_hass_color(self._color))

        self._is_on = True
        self.schedule_update_ha_state()


def _from_hass_brightness(brightness):
    """Convert Home Assistant brightness units to percentage."""
    return brightness / 255


def _from_hass_color(color):
    """Convert Home Assistant RGB list to Color tuple."""
    from pwmled import Color
    rgb = color_util.color_hs_to_RGB(*color)
    return Color(*tuple(rgb))
