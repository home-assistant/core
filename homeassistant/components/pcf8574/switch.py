"""Support for switch sensor using I2C PCF8574 chip."""
# https://github.com/oweidner/i2crelay/blob/master/i2crelay/i2crelay.py
# https://github.com/flyte/pcf8574
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_INVERT_LOGIC = 'invert_logic'
CONF_I2C_ADDRESS = 'i2c_address'
CONF_PINS = 'pins'
CONF_PULL_MODE = 'pull_mode'

DEFAULT_INVERT_LOGIC = False
DEFAULT_I2C_ADDRESS = 0x20

_SWITCHES_SCHEMA = vol.Schema({
    cv.positive_int: cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PINS): _SWITCHES_SCHEMA,
    vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
    vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS):
    vol.Coerce(int),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the PCF8574 devices."""
    from pcf8574 import PCF8574

    i2c_address = config.get(CONF_I2C_ADDRESS)

    if (i2c_address < 0x20 or i2c_address >= 0x20 + 8):
        raise ValueError(
            "Invalid device address: 0x%x for PCF8574" % (i2c_address,)
        )

    invert_logic = config.get(CONF_INVERT_LOGIC)

    _LOGGER.debug("setup_platform. i2c_address: %s, invert_logic:%s",
                  i2c_address, invert_logic,)

    # Rev 1 Pi uses 0
    # Rev 2 Pi uses 1
    pcf = PCF8574(1, i2c_address)

    switches = []
    pins = config.get(CONF_PINS)
    for pin_num, pin_name in pins.items():
        switches.append(PCF8574Switch(pin_name, pin_num, pcf, invert_logic))
        _LOGGER.debug(
            "address: %r pin: %r connected to: %r",
            i2c_address,
            pin_num,
            pcf,
        )

    add_entities(switches)


class PCF8574Switch(ToggleEntity):
    """Representation of a  PCF8574 output pin."""

    def __init__(self, pin_name, pin_num, pcf, invert_logic):
        """Initialize the pin."""
        #import digitalio
        self._pin_name = pin_name or DEVICE_DEFAULT_NAME
        self._pin_num = pin_num
        self._pcf = pcf
        self._invert_logic = invert_logic
        self._state = False

        self._pcf.port[self._pin_num] = False

        #self._pin.direction = digitalio.Direction.OUTPUT
        #self._pin.value = self._invert_logic

    @property
    def name(self):
        """Return the name of the switch."""
        return self._pin_name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        #self._pin.value = not self._invert_logic
        self._pcf.port[self._pin_num] = True
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        #self._pin.value = self._invert_logic
        self._pcf.port[self._pin_num] = False
        self._state = False
        self.schedule_update_ha_state()
