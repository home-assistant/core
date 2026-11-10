"""Climate entity for the air conditioner behind an Intesis gateway."""

from typing import Any, Final, override

from intesis_gw_modbus import FanSpeed, Mode, VanePosition

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_HAS_VANE
from .coordinator import IntesisConfigEntry, IntesisCoordinator
from .entity import IntesisEntity

PARALLEL_UPDATES = 1

MODE_TO_HVAC: Final = {
    Mode.AUTO: HVACMode.HEAT_COOL,
    Mode.HEAT: HVACMode.HEAT,
    Mode.DRY: HVACMode.DRY,
    Mode.FAN: HVACMode.FAN_ONLY,
    Mode.COOL: HVACMode.COOL,
}
HVAC_TO_MODE: Final = {hvac: mode for mode, hvac in MODE_TO_HVAC.items()}

FAN_TO_HA: Final = {
    FanSpeed.AUTO: FAN_AUTO,
    FanSpeed.LOW: FAN_LOW,
    FanSpeed.MEDIUM: FAN_MEDIUM,
    FanSpeed.HIGH: FAN_HIGH,
    FanSpeed.POWERFUL: "powerful",
}
HA_TO_FAN: Final = {name: speed for speed, name in FAN_TO_HA.items()}

VANE_TO_HA: Final = {position: position.value for position in VanePosition}
HA_TO_VANE: Final = {name: position for position, name in VANE_TO_HA.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntesisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the climate entity of the air conditioner behind the gateway."""
    async_add_entities(
        [IntesisClimate(entry.runtime_data, has_vane=entry.data[CONF_HAS_VANE])]
    )


class IntesisClimate(IntesisEntity, ClimateEntity):
    """The air conditioner behind an Intesis gateway."""

    _attr_name = None
    _attr_translation_key = "air_conditioner"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: IntesisCoordinator, *, has_vane: bool) -> None:
        """Bind to the air conditioner the gateway controls."""
        super().__init__(coordinator, "air_conditioner", "control")
        self._ac = coordinator.device
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        if has_vane:
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE

    @property
    @override
    def hvac_modes(self) -> list[HVACMode]:
        return [HVACMode.OFF, *(MODE_TO_HVAC[m] for m in self._ac.available_modes)]

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        if (power := self._ac.power) is None:
            return None
        if not power:
            return HVACMode.OFF
        if (mode := self._ac.mode) is None:
            return None
        return MODE_TO_HVAC[mode]

    @property
    @override
    def fan_modes(self) -> list[str]:
        return [FAN_TO_HA[s] for s in self._ac.available_fan_speeds]

    @property
    @override
    def fan_mode(self) -> str | None:
        speed = self._ac.fan_speed
        return None if speed is None else FAN_TO_HA[speed]

    @property
    @override
    def swing_modes(self) -> list[str]:
        return [VANE_TO_HA[p] for p in self._ac.available_vane_positions]

    @property
    @override
    def swing_mode(self) -> str | None:
        vane = self._ac.vane
        return None if vane is None else VANE_TO_HA[vane]

    @property
    @override
    def native_target_temperature(self) -> float | None:
        return self._ac.setpoint

    @property
    @override
    def native_current_temperature(self) -> float | None:
        return self._ac.current_temperature

    @property
    @override
    def min_temp(self) -> float:
        return self._ac.setpoint_min

    @property
    @override
    def max_temp(self) -> float:
        return self._ac.setpoint_max

    @property
    @override
    def target_temperature_step(self) -> float:
        return self._ac.setpoint_step

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self._async_write(lambda: self._async_apply_hvac_mode(hvac_mode))

    async def _async_apply_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode is HVACMode.OFF:
            await self._ac.async_set_power(False)
            return
        await self._ac.async_set_mode(HVAC_TO_MODE[hvac_mode])
        # The power read at the last poll can be stale, so always turn on
        await self._ac.async_set_power(True)

    @override
    async def async_turn_on(self) -> None:
        await self._async_write(lambda: self._ac.async_set_power(True))

    @override
    async def async_turn_off(self) -> None:
        await self._async_write(lambda: self._ac.async_set_power(False))

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        speed = HA_TO_FAN[fan_mode]
        await self._async_write(lambda: self._ac.async_set_fan_speed(speed))

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        position = HA_TO_VANE[swing_mode]
        await self._async_write(lambda: self._ac.async_set_vane(position))

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature: float = kwargs[ATTR_TEMPERATURE]
        hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode is not None:
            self._valid_mode_or_raise("hvac", hvac_mode, self.hvac_modes)

        async def _set_mode_and_setpoint() -> None:
            if hvac_mode is not None:
                await self._async_apply_hvac_mode(hvac_mode)
            await self._ac.async_set_setpoint(temperature)

        await self._async_write(_set_mode_and_setpoint)
