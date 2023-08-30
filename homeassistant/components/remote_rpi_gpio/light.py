"""Support for LED lights that can be controlled using PWM."""
from __future__ import annotations

import logging

from pwmled import Color
from pwmled.driver.gpio import GpioDriver
from pwmled.led import SimpleLed
from pwmled.led.rgb import RgbLed
from pwmled.led.rgbw import RgbwLed
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, STATE_ON
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

CONF_LEDS = "leds"
CONF_DRIVER = "driver"
CONF_PINS = "pins"
CONF_FREQUENCY = "frequency"

DEFAULT_BRIGHTNESS = 255
DEFAULT_COLOR = [0, 0]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_LEDS): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_NAME): cv.string,
                    vol.Required(CONF_PINS): vol.All(cv.ensure_list, [cv.positive_int]),
                    vol.Optional(CONF_FREQUENCY): cv.positive_int,
                    vol.Optional(CONF_HOST): cv.string,
                    vol.Optional(CONF_PORT): cv.positive_int,
                }
            ],
        )
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the PWM LED lights."""
    leds = []
    for led_conf in config[CONF_LEDS]:
        pins = led_conf[CONF_PINS]
        opt_args = {}

        if CONF_FREQUENCY in led_conf:
            opt_args["freq"] = led_conf[CONF_FREQUENCY]
        if CONF_HOST in led_conf:
            opt_args["host"] = led_conf[CONF_HOST]
        if CONF_PORT in led_conf:
            opt_args["port"] = led_conf[CONF_PORT]

        driver = GpioDriver(pins, **opt_args)

        name = led_conf[CONF_NAME]
        if len(pins) == 1:
            led = PwmSimpleLed(SimpleLed(driver), name)
        elif len(pins) == 3:
            led = PwmRgbLed(RgbLed(driver), name)
        elif len(pins) == 4:
            led = PwmRgbLed(RgbwLed(driver), name)
        else:
            _LOGGER.error(
                "Invalid number of pins: configure 1 (simple), 3 (RGB) or 4 (RGBW) pins to create a light"
            )
            return
        leds.append(led)

    add_entities(leds)


class PwmSimpleLed(LightEntity, RestoreEntity):
    """Representation of a simple one-color PWM LED."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, led, name):
        """Initialize one-color PWM LED."""
        self._led = led
        self._name = name
        self._is_on = False
        self._brightness = DEFAULT_BRIGHTNESS
        self._attr_supported_features |= LightEntityFeature.TRANSITION

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            self._is_on = last_state.state == STATE_ON
            self._brightness = last_state.attributes.get(
                "brightness", DEFAULT_BRIGHTNESS
            )

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

    def turn_on(self, **kwargs):
        """Turn on a led."""
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_TRANSITION in kwargs:
            transition_time = kwargs[ATTR_TRANSITION]
            self._led.transition(
                transition_time,
                is_on=True,
                brightness=_from_hass_brightness(self._brightness),
            )
        else:
            self._led.set(
                is_on=True, brightness=_from_hass_brightness(self._brightness)
            )

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

    _attr_color_mode = ColorMode.HS
    _attr_supported_color_modes = {ColorMode.HS}

    def __init__(self, led, name):
        """Initialize a RGB(W) PWM LED."""
        super().__init__(led, name)
        self._color = DEFAULT_COLOR
        self._attr_supported_features |= LightEntityFeature.TRANSITION

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            self._color = last_state.attributes.get("hs_color", DEFAULT_COLOR)

    @property
    def hs_color(self):
        """Return the color property."""
        return self._color

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
                color=_from_hass_color(self._color),
            )
        else:
            self._led.set(
                is_on=True,
                brightness=_from_hass_brightness(self._brightness),
                color=_from_hass_color(self._color),
            )

        self._is_on = True
        self.schedule_update_ha_state()


def _from_hass_brightness(brightness):
    """Convert Home Assistant brightness units to percentage."""
    return brightness / 255


def _from_hass_color(color):
    """Convert Home Assistant RGB list to Color tuple."""
    rgb = color_util.color_hs_to_RGB(*color)
    return Color(*tuple(rgb))
