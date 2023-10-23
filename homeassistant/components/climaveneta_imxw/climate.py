"""Support for the Mitsubishi-Climaveneta iMXW fancoil series."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_OFF,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.modbus import ModbusHub
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ClimavenetaIMXWCoordinator
from .const import (
    DOMAIN,
    MODE_OFF,
    MODE_ON,
    MODE_SUMMER,
    STATE_WRITE_FAN_SPEED_REGISTER,
    STATE_WRITE_MODE_REGISTER,
    STATE_WRITE_ON_OFF_REGISTER,
    TARGET_TEMPERATURE_SUMMER_REGISTER,
    TARGET_TEMPERATURE_WINTER_REGISTER,
)

_LOGGER = logging.getLogger(__name__)

CALL_TYPE_WRITE_REGISTER = "write_register"


class ClimavenetaIMXWClimate(
    CoordinatorEntity[ClimavenetaIMXWCoordinator], ClimateEntity
):
    """Representation of a ClimavenetaIMXW fancoil unit."""

    _attr_has_entity_name = True
    _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    _attr_fan_mode = FAN_AUTO

    _attr_hvac_mode = HVACMode.OFF
    _attr_hvac_modes = [
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.FAN_ONLY,
        HVACMode.OFF,
    ]

    _attr_swing_modes = [SWING_OFF]
    _attr_swing_mode = SWING_OFF

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    _filter_alarm: int | None = None
    _heat_recovery: int | None = None
    _heater_enabled: int | None = None
    _heating: int | None = None
    _cooling: int | None = None
    _alarm = False
    _summer_winter: int = 0
    _target_temperature_winter: int | None = None
    _attr_winter_temperature: float = 0.0
    _attr_summer_temperature: float = 0.0
    _exchanger_temperature: float = 0.0
    _t1_alarm: int = 0
    _t3_alarm: int = 0
    _water_drain: int = 0
    _min_temp: int = 15
    _max_temp: int = 30
    _attr_on_off: int = 0
    _attr_fan_only: int = 0
    _attr_ev_water: int = 0
    _attr_target_temperature: int = 0
    _attr_current_temperature: int = 0
    _attr_hvac_action: HVACAction = HVACAction.OFF

    def __init__(
        self, coordinator, hub: ModbusHub, modbus_slave: int | None, name: str | None
    ) -> None:
        """Initialize the unit."""
        super().__init__(coordinator)
        self._hub = hub
        self._attr_name = None
        self._slave = modbus_slave
        _attr_unique_id = f"{str(hub.name)}_{name}_{str(modbus_slave)}"

    async def async_update(self) -> None:
        """Update unit attributes."""

        # setpoint and actuals
        self._attr_target_temperature = self.coordinator.data_modbus[
            "target_temperature"
        ]
        self._attr_current_temperature = self.coordinator.data_modbus[
            "current_temperature"
        ]
        self._attr_on_off = self.coordinator.data_modbus["on_off"]
        self._attr_fan_only = self.coordinator.data_modbus["fan_only"]
        self._attr_hvac_action = self.coordinator.hvac_action
        self._attr_hvac_mode = self.coordinator.hvac_mode
        self._attr_fan_mode = self.coordinator.fan_mode

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (target_temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            _LOGGER.error("Received invalid temperature")
            return

        if self.coordinator.data_modbus["summer_winter"] == MODE_SUMMER:
            register = TARGET_TEMPERATURE_SUMMER_REGISTER
        else:
            register = TARGET_TEMPERATURE_WINTER_REGISTER

        if await self._async_write_int16_to_register(
            register, int(target_temperature * 10)
        ):
            self._attr_target_temperature = target_temperature
        else:
            _LOGGER.error("Modbus error setting target temperature to Climaveneta iMXW")

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if fan_mode in (FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH):
            if self.fan_modes and await self._async_write_int16_to_register(
                STATE_WRITE_FAN_SPEED_REGISTER, self.fan_modes.index(fan_mode)
            ):
                self._attr_fan_mode = fan_mode
            else:
                _LOGGER.error("Modbus error setting fan mode to Climaveneta iMXW")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self._async_write_int16_to_register(
                STATE_WRITE_ON_OFF_REGISTER, MODE_OFF
            )
        else:
            # if the device is off, then power it on and then set the mode
            if self._attr_on_off == MODE_OFF:
                await self._async_write_int16_to_register(
                    STATE_WRITE_ON_OFF_REGISTER, MODE_ON
                )
                self._attr_on_off = MODE_ON
            if self.hvac_modes and await self._async_write_int16_to_register(
                STATE_WRITE_MODE_REGISTER, self.hvac_modes.index(hvac_mode)
            ):
                self._attr_hvac_mode = hvac_mode
            else:
                _LOGGER.error("Modbus error setting fan mode to Climaveneta iMXW")

    async def _async_write_int16_to_register(self, register: int, value: int) -> bool:
        result = await self._hub.async_pb_call(
            self._slave, register, value, CALL_TYPE_WRITE_REGISTER
        )
        if not result:
            return False
        return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a config entry."""
    coordinator: ClimavenetaIMXWCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[ClimateEntity] = []

    entities.append(
        ClimavenetaIMXWClimate(
            coordinator, coordinator.hub, coordinator.slave_id, coordinator.name
        )
    )
    async_add_entities(entities)
