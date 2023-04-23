"""Platform for Flexit AC units with CI66 Modbus adapter."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.modbus import (
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CALL_TYPE_WRITE_REGISTER,
    CONF_HUB,
    DEFAULT_HUB,
    ModbusHub,
    get_hub,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_SLAVE,
    DEVICE_DEFAULT_NAME,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Required(CONF_SLAVE): vol.All(int, vol.Range(min=0, max=32)),
        vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Flexit Platform."""
    modbus_slave = config.get(CONF_SLAVE)
    name = config.get(CONF_NAME)
    hub = get_hub(hass, config[CONF_HUB])
    async_add_entities([Flexit(hub, modbus_slave, name)], True)


class Flexit(ClimateEntity):
    """Representation of a Flexit AC unit."""

    _attr_fan_modes = ["Off", "Low", "Medium", "High"]
    _attr_hvac_mode = HVACMode.COOL
    _attr_hvac_modes = [HVACMode.COOL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self, hub: ModbusHub, modbus_slave: int | None, name: str | None
    ) -> None:
        """Initialize the unit."""
        self._hub = hub
        self._attr_name = name
        self._slave = modbus_slave
        self._attr_fan_mode = None
        self._filter_hours: int | None = None
        self._filter_alarm: int | None = None
        self._heat_recovery: int | None = None
        self._heater_enabled: int | None = None
        self._heating: int | None = None
        self._cooling: int | None = None
        self._alarm = False
        self._outdoor_air_temp: float | None = None

    async def async_update(self) -> None:
        """Update unit attributes."""
        self._attr_target_temperature = await self._async_read_temp_from_register(
            CALL_TYPE_REGISTER_HOLDING, 8
        )
        self._attr_current_temperature = await self._async_read_temp_from_register(
            CALL_TYPE_REGISTER_INPUT, 9
        )
        res = await self._async_read_int16_from_register(CALL_TYPE_REGISTER_HOLDING, 17)
        if self.fan_modes and res < len(self.fan_modes):
            self._attr_fan_mode = self.fan_modes[res]
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
            self._attr_hvac_action = HVACAction.HEATING
        elif self._cooling:
            self._attr_hvac_action = HVACAction.COOLING
        elif self._heat_recovery:
            self._attr_hvac_action = HVACAction.IDLE
        elif actual_air_speed:
            self._attr_hvac_action = HVACAction.FAN
        else:
            self._attr_hvac_action = HVACAction.OFF

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
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

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (target_temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            _LOGGER.error("Received invalid temperature")
            return

        if await self._async_write_int16_to_register(8, int(target_temperature * 10)):
            self._attr_target_temperature = target_temperature
        else:
            _LOGGER.error("Modbus error setting target temperature to Flexit")

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if self.fan_modes and await self._async_write_int16_to_register(
            17, self.fan_modes.index(fan_mode)
        ):
            self._attr_fan_mode = fan_mode
        else:
            _LOGGER.error("Modbus error setting fan mode to Flexit")

    # Based on _async_read_register in ModbusThermostat class
    async def _async_read_int16_from_register(
        self, register_type: str, register: int
    ) -> int:
        """Read register using the Modbus hub slave."""
        result = await self._hub.async_pymodbus_call(
            self._slave, register, 1, register_type
        )
        if result is None:
            _LOGGER.error("Error reading value from Flexit modbus adapter")
            return -1

        return int(result.registers[0])

    async def _async_read_temp_from_register(
        self, register_type: str, register: int
    ) -> float:
        result = float(
            await self._async_read_int16_from_register(register_type, register)
        )
        if result == -1:
            return -1
        return result / 10.0

    async def _async_write_int16_to_register(self, register: int, value: int) -> bool:
        result = await self._hub.async_pymodbus_call(
            self._slave, register, value, CALL_TYPE_WRITE_REGISTER
        )
        if result == -1:
            return False
        return True
