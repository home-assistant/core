"""Support for Modbus fans."""
from __future__ import annotations

import logging

from homeassistant.components.fan import FanEntity
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_NAME,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .base_platform import BasePlatform
from .const import (
    CALL_TYPE_COIL,
    CALL_TYPE_WRITE_COIL,
    CALL_TYPE_WRITE_REGISTER,
    CONF_FANS,
    CONF_INPUT_TYPE,
    CONF_STATE_OFF,
    CONF_STATE_ON,
    CONF_VERIFY,
    CONF_WRITE_TYPE,
    MODBUS_DOMAIN,
)
from .modbus import ModbusHub

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
):
    """Read configuration and create Modbus fans."""
    if discovery_info is None:
        return
    fans = []

    for entry in discovery_info[CONF_FANS]:
        hub: ModbusHub = hass.data[MODBUS_DOMAIN][discovery_info[CONF_NAME]]
        fans.append(ModbusFan(hub, entry))
    async_add_entities(fans)


class ModbusFan(BasePlatform, FanEntity, RestoreEntity):
    """Base class representing a Modbus fan."""

    def __init__(self, hub: ModbusHub, config: dict) -> None:
        """Initialize the fan."""
        config[CONF_INPUT_TYPE] = ""
        super().__init__(hub, config)
        self._is_on = None
        if config[CONF_WRITE_TYPE] == CALL_TYPE_COIL:
            self._write_type = CALL_TYPE_WRITE_COIL
        else:
            self._write_type = CALL_TYPE_WRITE_REGISTER
        self._command_on = config[CONF_COMMAND_ON]
        self._command_off = config[CONF_COMMAND_OFF]
        if CONF_VERIFY in config:
            if config[CONF_VERIFY] is None:
                config[CONF_VERIFY] = {}
            self._verify_active = True
            self._verify_address = config[CONF_VERIFY].get(
                CONF_ADDRESS, config[CONF_ADDRESS]
            )
            self._verify_type = config[CONF_VERIFY].get(
                CONF_INPUT_TYPE, config[CONF_WRITE_TYPE]
            )
            self._state_on = config[CONF_VERIFY].get(CONF_STATE_ON, self._command_on)
            self._state_off = config[CONF_VERIFY].get(CONF_STATE_OFF, self._command_off)
        else:
            self._verify_active = False

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._is_on = state.state == STATE_ON

    @property
    def is_on(self):
        """Return true if fan is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs):
        """Set fan on."""

        result = await self._hub.async_pymodbus_call(
            self._slave, self._address, self._command_on, self._write_type
        )
        if result is None:
            self._available = False
            self.async_write_ha_state()
            return

        self._available = True
        if self._verify_active:
            await self.async_update()
            return

        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Set fan off."""
        result = await self._hub.async_pymodbus_call(
            self._slave, self._address, self._command_off, self._write_type
        )
        if result is None:
            self._available = False
            self.async_write_ha_state()
        else:
            self._available = True
            if self._verify_active:
                await self.async_update()
            else:
                self._is_on = False
                self.async_write_ha_state()

    async def async_update(self, now=None):
        """Update the entity state."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval
        if not self._verify_active:
            self._available = True
            self.async_write_ha_state()
            return

        result = await self._hub.async_pymodbus_call(
            self._slave, self._verify_address, 1, self._verify_type
        )
        if result is None:
            self._available = False
            self.async_write_ha_state()
            return

        self._available = True
        if self._verify_type == CALL_TYPE_COIL:
            self._is_on = bool(result.bits[0] & 1)
        else:
            value = int(result.registers[0])
            if value == self._state_on:
                self._is_on = True
            elif value == self._state_off:
                self._is_on = False
            elif value is not None:
                _LOGGER.error(
                    "Unexpected response from hub %s, slave %s register %s, got 0x%2x",
                    self._hub.name,
                    self._slave,
                    self._verify_address,
                    value,
                )
        self.async_write_ha_state()
