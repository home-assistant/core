"""Support for Modbus switches."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_SWITCHES,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType

from .const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_INPUT_TYPE,
    CONF_STATE_OFF,
    CONF_STATE_ON,
    CONF_VERIFY,
    CONF_WRITE_TYPE,
    MODBUS_DOMAIN,
)
from .modbus import ModbusHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None
):
    """Read configuration and create Modbus switches."""
    switches = []

    for entry in discovery_info[CONF_SWITCHES]:
        hub: ModbusHub = hass.data[MODBUS_DOMAIN][discovery_info[CONF_NAME]]
        switches.append(ModbusSwitch(hub, entry))
    async_add_entities(switches)


class ModbusSwitch(SwitchEntity, RestoreEntity):
    """Base class representing a Modbus switch."""

    def __init__(self, hub: ModbusHub, config: dict):
        """Initialize the switch."""
        self._hub: ModbusHub = hub
        self._name = config[CONF_NAME]
        self._slave = config.get(CONF_SLAVE)
        self._is_on = None
        self._available = True
        self._scan_interval = timedelta(seconds=config[CONF_SCAN_INTERVAL])
        self._address = config[CONF_ADDRESS]
        if config[CONF_WRITE_TYPE] == CALL_TYPE_COIL:
            self._write_func = self._hub.write_coil
            self._command_on = 0x01
            self._command_off = 0x00
        else:
            self._write_func = self._hub.write_register
            self._command_on = config[CONF_COMMAND_ON]
            self._command_off = config[CONF_COMMAND_OFF]
        if CONF_VERIFY in config:
            self._verify_active = True
            self._verify_address = config[CONF_VERIFY].get(
                CONF_ADDRESS, config[CONF_ADDRESS]
            )
            self._verify_type = config[CONF_VERIFY].get(
                CONF_INPUT_TYPE, config[CONF_WRITE_TYPE]
            )
            self._state_on = config[CONF_VERIFY].get(CONF_STATE_ON, self._command_on)
            self._state_off = config[CONF_VERIFY].get(CONF_STATE_OFF, self._command_off)

            if self._verify_type == CALL_TYPE_REGISTER_HOLDING:
                self._read_func = self._hub.read_holding_registers
            elif self._verify_type == CALL_TYPE_DISCRETE:
                self._read_func = self._hub.read_discrete_inputs
            elif self._verify_type == CALL_TYPE_REGISTER_INPUT:
                self._read_func = self._hub.read_input_registers
            else:  # self._verify_type == CALL_TYPE_COIL:
                self._read_func = self._hub.read_coils
        else:
            self._verify_active = False

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        state = await self.async_get_last_state()
        if state:
            self._is_on = state.state == STATE_ON

        async_track_time_interval(
            self.hass, lambda arg: self.update(), self._scan_interval
        )

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def turn_on(self, **kwargs):
        """Set switch on."""

        result = self._write_func(self._slave, self._address, self._command_on)
        if result is False:
            self._available = False
            self.schedule_update_ha_state()
        else:
            self._available = True
            if self._verify_active:
                self.update()
            else:
                self._is_on = True
                self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Set switch off."""
        result = self._write_func(self._slave, self._address, self._command_off)
        if result is False:
            self._available = False
            self.schedule_update_ha_state()
        else:
            self._available = True
            if self._verify_active:
                self.update()
            else:
                self._is_on = False
                self.schedule_update_ha_state()

    def update(self):
        """Update the entity state."""
        if not self._verify_active:
            self._available = True
            self.schedule_update_ha_state()
            return

        result = self._read_func(self._slave, self._verify_address, 1)
        if result is None:
            self._available = False
            self.schedule_update_ha_state()
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
        self.schedule_update_ha_state()
