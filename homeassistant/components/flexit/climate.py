"""Platform for Flexit AC units with CI66 Modbus adapter."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.components.modbus import get_hub
from homeassistant.components.modbus.const import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CALL_TYPE_WRITE_REGISTER,
    CONF_HUB,
    DEFAULT_HUB,
)
from homeassistant.components.modbus.modbus import ModbusHub
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_SLAVE,
    DEVICE_DEFAULT_NAME,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Required(CONF_SLAVE): vol.All(int, vol.Range(min=0, max=32)),
        vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities,
    discovery_info: DiscoveryInfoType = None,
):
    """Set up the Flexit Platform."""
    modbus_slave = config.get(CONF_SLAVE)
    name = config.get(CONF_NAME)
    hub = get_hub(hass, config[CONF_HUB])
    async_add_entities([Flexit(hub, modbus_slave, name)], True)


class Flexit(ClimateEntity):
    """Representation of a Flexit AC unit."""

    def __init__(
        self, hub: ModbusHub, modbus_slave: int | None, name: str | None
    ) -> None:
        """Initialize the unit."""
        self._hub = hub
        self._name = name
        self._slave = modbus_slave
        self._target_temperature = None
        self._current_temperature = None
        self._current_fan_mode = None
        self._current_operation = None
        self._fan_modes = ["Off", "Low", "Medium", "High"]
        self._current_operation = None
        self._filter_hours = None
        self._filter_alarm = None
        self._heat_recovery = None
        self._heater_enabled = False
        self._heating = None
        self._cooling = None
        self._alarm = False
        self._outdoor_air_temp = None

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    async def async_update(self):
        """Update unit attributes."""
        self._target_temperature = await self._async_read_temp_from_register(
            CALL_TYPE_REGISTER_HOLDING, 8
        )
        self._current_temperature = await self._async_read_temp_from_register(
            CALL_TYPE_REGISTER_INPUT, 9
        )
        res = await self._async_read_int16_from_register(CALL_TYPE_REGISTER_HOLDING, 17)
        if res < len(self._fan_modes):
            self._current_fan_mode = res
        self._filter_hours = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_INPUT, 8
        )
        # # Mechanical heat recovery, 0-100%
        self._heat_recovery = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_INPUT, 14
        )
        # # Heater active 0-100%
        self._heating = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_INPUT, 15
        )
        # # Cooling active 0-100%
        self._cooling = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_INPUT, 13
        )
        # # Filter alarm 0/1
        self._filter_alarm = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_INPUT, 27
        )
        # # Heater enabled or not. Does not mean it's necessarily heating
        self._heater_enabled = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_INPUT, 28
        )
        self._outdoor_air_temp = await self._async_read_temp_from_register(
            CALL_TYPE_REGISTER_INPUT, 11
        )

        actual_air_speed = await self._async_read_int16_from_register(
            CALL_TYPE_REGISTER_INPUT, 48
        )

        if self._heating:
            self._current_operation = "Heating"
        elif self._cooling:
            self._current_operation = "Cooling"
        elif self._heat_recovery:
            self._current_operation = "Recovering"
        elif actual_air_speed:
            self._current_operation = "Fan Only"
        else:
            self._current_operation = "Off"

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return {
            "filter_hours": self._filter_hours,
            "filter_alarm": self._filter_alarm,
            "heat_recovery": self._heat_recovery,
            "heating": self._heating,
            "heater_enabled": self._heater_enabled,
            "cooling": self._cooling,
            "outdoor_air_temp": self._outdoor_air_temp,
        }

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_COOL]

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._fan_modes

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            target_temperature = kwargs.get(ATTR_TEMPERATURE)
        else:
            _LOGGER.error("Received invalid temperature")
            return

        if await self._async_write_int16_to_register(8, target_temperature * 10):
            self._target_temperature = target_temperature
        else:
            _LOGGER.error("Modbus error setting target temperature to Flexit")

    async def async_set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        if await self._async_write_int16_to_register(
            17, self.fan_modes.index(fan_mode)
        ):
            self._current_fan_mode = self.fan_modes.index(fan_mode)
        else:
            _LOGGER.error("Modbus error setting fan mode to Flexit")

    # Based on _async_read_register in ModbusThermostat class
    async def _async_read_int16_from_register(self, register_type, register) -> int:
        """Read register using the Modbus hub slave."""
        result = await self._hub.async_pymodbus_call(
            self._slave, register, 1, register_type
        )
        if result is None:
            _LOGGER.error("Error reading value from Flexit modbus adapter")
            return -1

        return int(result.registers[0])

    async def _async_read_temp_from_register(self, register_type, register) -> float:
        result = float(
            await self._async_read_int16_from_register(register_type, register)
        )
        if result == -1:
            return -1
        return result / 10.0

    async def _async_write_int16_to_register(self, register, value) -> bool:
        value = int(value)
        result = await self._hub.async_pymodbus_call(
            self._slave, register, value, CALL_TYPE_WRITE_REGISTER
        )
        if result == -1:
            return False
        return True
