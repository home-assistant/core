"""Support for Dyson infrared heater/coolers (AM09)."""

import asyncio
from typing import Any, override

from infrared_protocols.codes.dyson.am09 import DysonAm09Code

from homeassistant.components.climate import (
    SWING_OFF,
    SWING_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_COMMAND_STEP_DELAY,
    CONF_INFRARED_EMITTER_ENTITY_ID,
    DEFAULT_COMMAND_STEP_DELAY,
    DOMAIN,
)

PARALLEL_UPDATES = 0

_MIN_TEMP = 1
_MAX_TEMP = 37

_SPEED_COUNT = 10
_FAN_MODES = [str(speed) for speed in range(1, _SPEED_COUNT + 1)]

PRESET_FOCUSED = "focused"
PRESET_DIFFUSED = "diffused"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Dyson infrared heater/cooler platform from a config entry."""
    infrared_emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    step_delay = entry.data.get(CONF_COMMAND_STEP_DELAY, DEFAULT_COMMAND_STEP_DELAY)
    async_add_entities(
        [
            DysonInfraredHeaterCooler(
                infrared_emitter_entity_id, entry.entry_id, entry.title, step_delay
            )
        ]
    )


class DysonInfraredHeaterCooler(InfraredEmitterConsumerEntity, ClimateEntity):
    """Representation of a Dyson AM09 heater/cooler entity."""

    _attr_translation_key = "heater_cooler"
    _attr_has_entity_name = True
    _attr_assumed_state = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = _MIN_TEMP
    _attr_max_temp = _MAX_TEMP
    _attr_target_temperature_step = 1.0
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT]
    _attr_fan_modes = _FAN_MODES
    _attr_preset_modes = [PRESET_FOCUSED, PRESET_DIFFUSED]
    _attr_swing_modes = [SWING_OFF, SWING_ON]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.SWING_MODE
    )

    def __init__(
        self,
        infrared_emitter_entity_id: str,
        unique_id: str,
        name: str,
        step_delay: float = DEFAULT_COMMAND_STEP_DELAY,
    ) -> None:
        """Initialize the Dyson infrared heater/cooler entity."""
        self._infrared_emitter_entity_id = infrared_emitter_entity_id
        self._step_delay = step_delay

        self._attr_unique_id = unique_id
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = float(_MIN_TEMP)
        self._attr_fan_mode = _FAN_MODES[_SPEED_COUNT // 2 - 1]
        self._attr_preset_mode = PRESET_DIFFUSED
        self._attr_swing_mode = SWING_OFF

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=name,
        )

    async def _async_send_am09_action(self, code: DysonAm09Code) -> None:
        await self._send_command(code.to_command())

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode.

        AM09 has no dedicated OFF code, only a power toggle (ON), so leaving
        HEAT/COOL relies on the assumed state matching the physical device.
        """
        if hvac_mode == self._attr_hvac_mode:
            return

        if hvac_mode is HVACMode.OFF:
            await self._async_send_am09_action(DysonAm09Code.ON)
        else:
            if self._attr_hvac_mode is HVACMode.OFF:
                await self._async_send_am09_action(DysonAm09Code.ON)
                await asyncio.sleep(self._step_delay)
            if hvac_mode is HVACMode.COOL:
                await self._async_send_am09_action(DysonAm09Code.COOL_ON)
            elif hvac_mode is HVACMode.HEAT:
                await self._async_send_am09_action(DysonAm09Code.HEAT_UP)
                self._attr_target_temperature = float(_MIN_TEMP)

        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature by stepping HEAT_UP/HEAT_DOWN."""
        if self._attr_hvac_mode is not HVACMode.HEAT:
            return

        target = max(_MIN_TEMP, min(_MAX_TEMP, int(kwargs[ATTR_TEMPERATURE])))
        current = int(self._attr_target_temperature or _MIN_TEMP)
        if target == current:
            return

        code = DysonAm09Code.HEAT_UP if target > current else DysonAm09Code.HEAT_DOWN
        for _ in range(abs(target - current)):
            await self._async_send_am09_action(code)
            await asyncio.sleep(self._step_delay)

        self._attr_target_temperature = float(target)
        self.async_write_ha_state()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan speed by stepping SPEED_UP/SPEED_DOWN."""
        target = int(fan_mode)
        current = int(self._attr_fan_mode or _FAN_MODES[0])
        if target == current:
            return

        code = DysonAm09Code.SPEED_UP if target > current else DysonAm09Code.SPEED_DOWN
        for _ in range(abs(target - current)):
            await self._async_send_am09_action(code)
            await asyncio.sleep(self._step_delay)

        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Toggle oscillation."""
        await self._async_send_am09_action(DysonAm09Code.SWING)
        self._attr_swing_mode = swing_mode
        self.async_write_ha_state()

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the airflow diffusion preset."""
        code = (
            DysonAm09Code.VENT_THIN
            if preset_mode == PRESET_FOCUSED
            else DysonAm09Code.VENT_WIDE
        )
        await self._async_send_am09_action(code)
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()
