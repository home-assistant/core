"""Support for numbers that can be controlled using PWM."""
from __future__ import annotations

import logging
from typing import Any

from pwmled.driver.gpio import GpioDriver
from pwmled.driver.pca9685 import Pca9685Driver
import voluptuous as vol

from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    PLATFORM_SCHEMA,
    NumberEntity,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_HOST,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_MODE,
    CONF_NAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ATTR_FREQUENCY,
    ATTR_INVERT,
    CONF_DRIVER,
    CONF_DRIVER_GPIO,
    CONF_DRIVER_PCA9685,
    CONF_DRIVER_TYPES,
    CONF_FREQUENCY,
    CONF_INVERT,
    CONF_NUMBERS,
    CONF_PIN,
    CONF_STEP,
    MODE_AUTO,
    MODE_BOX,
    MODE_SLIDER,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NUMBERS): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_NAME): cv.string,
                    vol.Required(CONF_DRIVER): vol.In(CONF_DRIVER_TYPES),
                    vol.Required(CONF_PIN): cv.positive_int,
                    vol.Optional(CONF_INVERT, default=False): cv.boolean,
                    vol.Optional(CONF_FREQUENCY): cv.positive_int,
                    vol.Optional(CONF_ADDRESS): cv.byte,
                    vol.Optional(CONF_HOST): cv.string,
                    vol.Optional(CONF_MINIMUM, default=DEFAULT_MIN_VALUE): vol.Coerce(
                        float
                    ),
                    vol.Optional(CONF_MAXIMUM, default=DEFAULT_MAX_VALUE): vol.Coerce(
                        float
                    ),
                    vol.Optional(CONF_STEP, default=DEFAULT_STEP): cv.positive_float,
                    vol.Optional(CONF_MODE, default=MODE_SLIDER): vol.In(
                        [MODE_BOX, MODE_SLIDER, MODE_AUTO]
                    ),
                }
            ],
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the PWM-output numbers."""
    numbers = []
    for number_conf in config[CONF_NUMBERS]:
        driver_type = number_conf[CONF_DRIVER]
        pin = number_conf[CONF_PIN]
        opt_args = {}
        if CONF_FREQUENCY in number_conf:
            opt_args["freq"] = number_conf[CONF_FREQUENCY]
        if driver_type == CONF_DRIVER_GPIO:
            if CONF_HOST in number_conf:
                opt_args["host"] = number_conf[CONF_HOST]
            driver = GpioDriver([pin], **opt_args)
        elif driver_type == CONF_DRIVER_PCA9685:
            if CONF_ADDRESS in number_conf:
                opt_args["address"] = number_conf[CONF_ADDRESS]
            driver = Pca9685Driver([pin], **opt_args)
        else:
            _LOGGER.error("Invalid driver type")
            return

        number = PwmNumber(hass, number_conf, driver)
        numbers.append(number)

    add_entities(numbers)


class PwmNumber(NumberEntity, RestoreEntity):
    """Representation of a simple  PWM output."""

    def __init__(self, hass, config, driver):
        """Initialize one-color PWM LED."""
        self._driver = driver
        self._config = config
        self._hass = hass
        self._attr_min_value = config[CONF_MINIMUM]
        self._attr_max_value = config[CONF_MAXIMUM]
        self._attr_step = config[CONF_STEP]
        self._attr_mode = config[CONF_MODE]
        self._attr_value = config[CONF_MINIMUM]

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            await self.async_set_value(float(last_state.state))

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the number."""
        return self._config[CONF_NAME]

    @property
    def frequency(self):
        """Return PWM frequency."""
        return self._config[CONF_FREQUENCY]

    @property
    def invert(self):
        """Return if output is inverted."""
        return self._config[CONF_INVERT]

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        attr = super().capability_attributes
        attr[ATTR_FREQUENCY] = self.frequency
        attr[ATTR_INVERT] = self.invert
        return attr

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        # Clip value to limits (don't know if this is required?)
        if value < self._config[CONF_MINIMUM]:
            value = self._config[CONF_MINIMUM]
        if value > self._config[CONF_MAXIMUM]:
            value = self._config[CONF_MAXIMUM]

        # Scale range from 0..100 to 0..255 (gpio) or 0..65535 (pca9685)
        max_pwm = 255.0
        if self._config[CONF_DRIVER] == CONF_DRIVER_PCA9685:
            max_pwm = 65535.0
        # In case the invert bit is on, invert the value
        used_value = value
        if self._config[CONF_INVERT]:
            used_value = 100.0 - value
        # Scale to range of the driver
        scaled_value = int(round((used_value / 100.0) * max_pwm))
        # Set value to driver
        self._driver._set_pwm([scaled_value])  # pylint: disable=W0212
        self._attr_value = value
        self.schedule_update_ha_state()
