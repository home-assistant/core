"""Platform for mcp23017-based switch."""

import functools
import logging

import voluptuous as vol

from homeassistant.components.mcp23017 import MCP23017
from homeassistant.components.switch import PLATFORM_SCHEMA, ToggleEntity
from homeassistant.const import DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, DOMAIN_I2C

_LOGGER = logging.getLogger(__name__)

CONF_PINS = "pins"
CONF_INVERT_LOGIC = "invert_logic"
CONF_PULL_MODE = "pull_mode"
CONF_I2C_ADDRESS = "i2c_address"

DEFAULT_INVERT_LOGIC = False
DEFAULT_I2C_ADDRESS = 0x20

_SWITCHES_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PINS): _SWITCHES_SCHEMA,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.Coerce(int),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the MCP23017 for switch entities."""

    # Bail out if i2c device manager is not available
    if DOMAIN_I2C not in hass.data:
        _LOGGER.warning(
            "Umable to setup %s switch (missing %s platform)", DOMAIN, DOMAIN_I2C
        )
        return

    pins = config[CONF_PINS]
    invert_logic = config[CONF_INVERT_LOGIC]

    i2c_address = config[CONF_I2C_ADDRESS]
    i2c_bus = hass.data[DOMAIN_I2C]

    switches = []
    for pin_num, pin_name in pins.items():
        switch_entity = MCP23017Switch(pin_num, pin_name, invert_logic)
        if await hass.async_add_executor_job(
            functools.partial(switch_entity.bind, MCP23017, i2c_bus, i2c_address)
        ):
            switches.append(switch_entity)

    async_add_entities(switches, False)


class MCP23017Switch(ToggleEntity):
    """Represent a switch that uses MCP23017."""

    def __init__(self, pin_num, pin_name, invert_logic):
        """Initialize the MCP23017 switch."""
        self._name = pin_name or DEVICE_DEFAULT_NAME
        self._pin_num = pin_num
        self._invert_logic = invert_logic
        self._device = None
        self._state = False

        _LOGGER.info(
            "%s(pin %d:'%s') created",
            type(self).__name__,
            pin_num,
            pin_name,
        )

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self.hass.async_add_executor_job(
            functools.partial(
                self._device.set_pin_value, self._pin_num, not self._invert_logic
            )
        )
        self._state = True
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self.hass.async_add_executor_job(
            functools.partial(
                self._device.set_pin_value, self._pin_num, self._invert_logic
            )
        )
        self._state = False
        self.schedule_update_ha_state()

    # Sync functions executed outside of hass async loop.

    def bind(self, device_class, bus, address):
        """Register a device to the given {bus, address}.

        This function should be called from the thread pool (call blocking functions).
        """
        # Bind a MCP23017 device to this switch entity
        self._device = bus.register_device(device_class, address)
        if self._device:
            # Default device configuration for a switch
            self._device.set_input(self._pin_num, False)
            self._state = self._device.get_pin_value(self._pin_num)

            _LOGGER.info(
                "%s(pin %d:'%s') attached to I2C device@0x%02x",
                type(self).__name__,
                self._pin_num,
                self._name,
                address,
            )
        else:
            _LOGGER.warning(
                "Failed to bind %s(pin %d:'%s') to I2C device@0x%02x",
                type(self).__name__,
                self._pin_num,
                self._name,
                address,
            )

        return self._device
