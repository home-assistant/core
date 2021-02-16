"""Platform for mcp23017-based binary_sensor."""

import asyncio
import functools
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
import homeassistant.components.mcp23017 as mcp23017
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_FLOW_PIN_NAME,
    CONF_FLOW_PIN_NUMBER,
    CONF_FLOW_PLATFORM,
    CONF_I2C_ADDRESS,
    CONF_INVERT_LOGIC,
    CONF_PINS,
    CONF_PULL_MODE,
    DEFAULT_I2C_ADDRESS,
    DEFAULT_INVERT_LOGIC,
    DEFAULT_PULL_MODE,
    DOMAIN,
    MODE_DOWN,
    MODE_UP,
)

_LOGGER = logging.getLogger(__name__)

_PIN_SCHEMA = vol.Schema({cv.positive_int: cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PINS): _PIN_SCHEMA,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
        vol.Optional(CONF_PULL_MODE, default=DEFAULT_PULL_MODE): vol.All(
            vol.Upper, vol.In([MODE_UP, MODE_DOWN])
        ),
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.Coerce(int),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the MCP23017 platform for binary_sensor entities."""

    for pin_number, pin_name in config[CONF_PINS].items():
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_FLOW_PLATFORM: "binary_sensor",
                    CONF_FLOW_PIN_NUMBER: pin_number,
                    CONF_FLOW_PIN_NAME: pin_name,
                    CONF_I2C_ADDRESS: config[CONF_I2C_ADDRESS],
                    CONF_INVERT_LOGIC: config[CONF_INVERT_LOGIC],
                    CONF_PULL_MODE: config[CONF_PULL_MODE],
                },
            )
        )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a MCP23017 binary_sensor entry."""

    binary_sensor_entity = MCP23017BinarySensor(hass, config_entry)
    binary_sensor_entity.device = await mcp23017.async_get_or_create(
        hass, config_entry, binary_sensor_entity
    )

    if await hass.async_add_executor_job(binary_sensor_entity.configure_device):
        async_add_entities([binary_sensor_entity])


async def async_unload_entry(hass, config_entry):
    """Unload MCP23017 switch entry corresponding to config_entry."""
    print("FIXME ?")


class MCP23017BinarySensor(BinarySensorEntity):
    """Represent a binary sensor that uses MCP23017."""

    def __init__(self, hass, config_entry):
        """Initialize the MCP23017 binary sensor."""
        self._state = None
        self._device = None

        self._i2c_address = config_entry.data[CONF_I2C_ADDRESS]
        self._pin_name = config_entry.data[CONF_FLOW_PIN_NAME]
        self._pin_number = config_entry.data[CONF_FLOW_PIN_NUMBER]

        self._invert_logic = config_entry.data.get(
            CONF_INVERT_LOGIC, DEFAULT_INVERT_LOGIC
        )
        self._pull_mode = config_entry.data.get(CONF_PULL_MODE, DEFAULT_PULL_MODE)

        # Create or update option values for binary_sensor platform
        hass.config_entries.async_update_entry(
            config_entry,
            options={
                CONF_INVERT_LOGIC: self._invert_logic,
                CONF_PULL_MODE: self._pull_mode,
            },
        )

        # Subscribe to updates of config entry options.
        self._unsubscribe_update_listener = config_entry.add_update_listener(
            self.async_config_update
        )

        _LOGGER.info(
            "%s(pin %d:'%s') created",
            type(self).__name__,
            self._pin_number,
            self._pin_name,
        )

    @property
    def icon(self):
        """Return device icon for this entity."""
        return "mdi:chip"

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self._device.unique_id}-0x{self._pin_number:02x}"

    @property
    def should_poll(self):
        """No polling needed from homeassistant for this entity."""
        return False

    @property
    def name(self):
        """Return the name of the entity."""
        return self._pin_name

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._state != self._invert_logic

    @property
    def pin(self):
        """Return the pin number of the entity."""
        return self._pin_number

    @property
    def address(self):
        """Return the i2c address of the entity."""
        return self._i2c_address

    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {(DOMAIN, self._i2c_address)},
            "manufacturer": "Microchip",
            "model": "MCP23017",
            "entry_type": "service",
        }

    @property
    def device(self):
        """Get device property."""
        return self._device

    @device.setter
    def device(self, value):
        """Set device property."""
        self._device = value

    @callback
    async def async_push_update(self, state):
        """Update the GPIO state."""
        self._state = state
        self.async_schedule_update_ha_state()

    @callback
    async def async_config_update(self, hass, config_entry):
        """Handle update from config entry options."""
        self._invert_logic = config_entry.options[CONF_INVERT_LOGIC]
        if self._pull_mode != config_entry.options[CONF_PULL_MODE]:
            self._pull_mode = config_entry.options[CONF_PULL_MODE]
            await hass.async_add_executor_job(
                functools.partial(
                    self._device.set_pullup,
                    self._pin_number,
                    bool(self._pull_mode == MODE_UP),
                )
            )
        self.async_schedule_update_ha_state()

    def unsubscribe_update_listener(self):
        """Remove listener from config entry options."""
        self._unsubscribe_update_listener()

    # Sync functions executed outside of the hass async loop

    def push_update(self, state):
        """Signal a state change and call the async counterpart."""
        asyncio.run_coroutine_threadsafe(self.async_push_update(state), self.hass.loop)

    def configure_device(self):
        """Attach instance to a device on the given address and configure it.

        This function should be called from the thread pool as it contains blocking functions.

        Return True when successful.
        """
        if self._device:
            # Configure entity as input for a binary sensor
            self._device.set_input(self._pin_number, True)
            self._device.set_pullup(self._pin_number, bool(self._pull_mode == MODE_UP))

            return True

        return False
