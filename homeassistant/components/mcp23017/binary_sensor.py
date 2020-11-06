"""Platform for mcp23017-based binary_sensor."""

import asyncio
import functools
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.components.mcp23017 import MCP23017
from homeassistant.const import DEVICE_DEFAULT_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, DOMAIN_I2C

_LOGGER = logging.getLogger(__name__)

CONF_PINS = "pins"
CONF_INVERT_LOGIC = "invert_logic"
CONF_PULL_MODE = "pull_mode"
CONF_I2C_ADDRESS = "i2c_address"
CONF_SCAN_MULTIPLE = "scan_slowdown"

MODE_UP = "UP"
MODE_DOWN = "DOWN"

DEFAULT_INVERT_LOGIC = False
DEFAULT_PULL_MODE = MODE_UP
DEFAULT_SCAN_MULTIPLE = 10
DEFAULT_I2C_ADDRESS = 0x20

_PIN_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PINS): _PIN_SCHEMA,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
        vol.Optional(CONF_PULL_MODE, default=DEFAULT_PULL_MODE): vol.All(
            vol.Upper, vol.In([MODE_UP, MODE_DOWN])
        ),
        vol.Optional(CONF_SCAN_MULTIPLE, default=DEFAULT_SCAN_MULTIPLE): vol.Coerce(
            int
        ),
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.Coerce(int),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the MCP23017 platform for binary_sensor entities."""

    # Bail out if i2c device manager is not available
    if DOMAIN_I2C not in hass.data:
        _LOGGER.warning(
            "Umable to setup %s binary_sensors (missing %s platform)",
            DOMAIN,
            DOMAIN_I2C,
        )
        return

    pins = config[CONF_PINS]
    invert_logic = config[CONF_INVERT_LOGIC]
    pull_mode = config[CONF_PULL_MODE]
    scan_slowdown = config[CONF_SCAN_MULTIPLE]

    i2c_address = config[CONF_I2C_ADDRESS]
    i2c_bus = hass.data[DOMAIN_I2C]

    binary_sensors = []
    for pin_num, pin_name in pins.items():
        binary_sensor_entity = MCP23017BinarySensor(
            pin_num, pin_name, invert_logic, pull_mode
        )
        if await hass.async_add_executor_job(
            functools.partial(
                binary_sensor_entity.bind, MCP23017, i2c_bus, i2c_address, scan_slowdown
            )
        ):
            binary_sensors.append(binary_sensor_entity)

    async_add_entities(binary_sensors, False)


class MCP23017BinarySensor(BinarySensorEntity):
    """Represent a binary sensor that uses MCP23017."""

    def __init__(self, pin_num, pin_name, invert_logic, pull_mode):
        """Initialize the MCP23017 binary sensor."""
        self._name = pin_name or DEVICE_DEFAULT_NAME
        self._pin_num = pin_num
        self._invert_logic = invert_logic
        self._pull_mode = pull_mode
        self._device = None
        self._state = None

        _LOGGER.info("%s(pin %d:'%s') created", type(self).__name__, pin_num, pin_name)

    @property
    def should_poll(self):
        """No polling needed from homeassistant for this entity."""
        return False

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._state != self._invert_logic

    @callback
    async def async_input_callback(self, state):
        """Update the GPIO state."""
        self._state = state
        await self.async_schedule_update_ha_state()

    # Sync functions executed outside of the hass async loop

    def input_callback(self, state):
        """Signal a state change and call the async counterpart."""
        asyncio.run_coroutine_threadsafe(
            self.async_input_callback(state), self.hass.loop
        )

    def bind(self, device_class, bus, address, scan_slowdown):
        """Register a device to the given {bus, address}.

        This function should be called from the thread pool (call blocking functions).
        """
        # Bind a MCP23017 device to this binary_sensor entity
        self._device = bus.register_device(device_class, address, scan_slowdown)

        if self._device:
            # Default device configuration for a binary_sensor
            self._device.set_input(self._pin_num, True)
            self._device.set_pullup(self._pin_num, bool(self._pull_mode == MODE_UP))
            self._device.register_input_callback(self._pin_num, self.input_callback)

            _LOGGER.info(
                "%s(pin %d:'%s') bound to I2C device@0x%02x",
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
