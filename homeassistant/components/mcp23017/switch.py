"""Platform for mcp23017-based switch."""

import functools
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, ToggleEntity
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
    DEFAULT_I2C_ADDRESS,
    DEFAULT_INVERT_LOGIC,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

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

    for pin_number, pin_name in config[CONF_PINS].items():
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_FLOW_PLATFORM: "switch",
                    CONF_FLOW_PIN_NUMBER: pin_number,
                    CONF_FLOW_PIN_NAME: pin_name,
                    CONF_I2C_ADDRESS: config[CONF_I2C_ADDRESS],
                    CONF_INVERT_LOGIC: config[CONF_INVERT_LOGIC],
                },
            )
        )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a MCP23017 switch entry."""

    switch_entity = MCP23017Switch(hass, config_entry)

    if await hass.async_add_executor_job(switch_entity.configure_device):
        async_add_entities([switch_entity])


# async def async_unload_entry(hass, config_entry):
#    """Unload MCP23017 switch entry corresponding to config_entry."""


class MCP23017Switch(ToggleEntity):
    """Represent a switch that uses MCP23017."""

    def __init__(self, hass, config_entry):
        """Initialize the MCP23017 switch."""
        self._hass = hass
        self._i2c_address = config_entry.data[CONF_I2C_ADDRESS]
        self._pin_name = config_entry.data[CONF_FLOW_PIN_NAME]
        self._pin_number = config_entry.data[CONF_FLOW_PIN_NUMBER]

        self._invert_logic = config_entry.data.get(
            CONF_INVERT_LOGIC, DEFAULT_INVERT_LOGIC
        )

        # Create or update option values for switch platform
        self._hass.config_entries.async_update_entry(
            config_entry,
            options={
                CONF_INVERT_LOGIC: self._invert_logic,
            },
        )

        # Subscribe to updates of config entry options
        self._unsubscribe_update_listener = config_entry.add_update_listener(
            self.async_config_update
        )

        # Retrieve associated device
        self._device = self._hass.data[DOMAIN][config_entry.data[CONF_I2C_ADDRESS]]
        self._state = None

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
        return f"{self._device.unique_id}-{self._pin_number}"

    @property
    def name(self):
        """Return the name of the switch."""
        return self._pin_name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def pin(self):
        """Return the pin number of the entity."""
        return self._pin_number

    @property
    def device_info(self):
        """Device info."""
        return {
            "identifiers": {(DOMAIN, self._i2c_address)},
            "manufacturer": "Microchip",
            "model": "MCP23017",
            "entry_type": "service",
        }

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self.hass.async_add_executor_job(
            functools.partial(
                self._device.set_pin_value, self._pin_number, not self._invert_logic
            )
        )
        self._state = True
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self.hass.async_add_executor_job(
            functools.partial(
                self._device.set_pin_value, self._pin_number, self._invert_logic
            )
        )
        self._state = False
        self.schedule_update_ha_state()

    @callback
    async def async_config_update(self, hass, config_entry):
        """Handle update from config entry options."""
        self._invert_logic = config_entry.options[CONF_INVERT_LOGIC]
        await self.hass.async_add_executor_job(
            functools.partial(
                self._device.set_pin_value,
                self._pin_number,
                self._state ^ self._invert_logic,
            )
        )
        self.async_schedule_update_ha_state()

    def unsubscribe_update_listener(self):
        """Remove listener from config entry options."""
        self._unsubscribe_update_listener()

    # Sync functions executed outside of hass async loop.

    def configure_device(self):
        """Attach instance to a device on the given address and configure it.

        This function should be called from the thread pool as it contains blocking functions.

        Return True when successful.
        """
        if self._device:
            # Register entity
            if self._device.register_entity(self):
                # Configure entity as output for a switch
                self._device.set_input(self._pin_number, False)
                self._state = self._device.get_pin_value(self._pin_number)

                return True

        return False
