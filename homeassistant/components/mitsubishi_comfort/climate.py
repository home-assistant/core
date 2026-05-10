"""Climate entity for Mitsubishi Comfort integration."""

from typing import Any

from mitsubishi_comfort import FanSpeed, IndoorUnit, Mode, VaneDirection

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MitsubishiComfortConfigEntry, MitsubishiComfortCoordinator
from .entity import MitsubishiComfortEntity

_MODE_TO_HVAC: dict[str, HVACMode] = {
    "off": HVACMode.OFF,
    "cool": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "dry": HVACMode.DRY,
    "vent": HVACMode.FAN_ONLY,
    "auto": HVACMode.HEAT_COOL,
    "autoCool": HVACMode.HEAT_COOL,
    "autoHeat": HVACMode.HEAT_COOL,
}

_HVAC_TO_MODE: dict[HVACMode, Mode] = {
    HVACMode.OFF: Mode.OFF,
    HVACMode.COOL: Mode.COOL,
    HVACMode.HEAT: Mode.HEAT,
    HVACMode.DRY: Mode.DRY,
    HVACMode.FAN_ONLY: Mode.FAN,
    HVACMode.HEAT_COOL: Mode.AUTO,
}

_LIB_MODE_TO_HVAC: dict[Mode, HVACMode] = {v: k for k, v in _HVAC_TO_MODE.items()}

_MODE_TO_ACTION: dict[str, HVACAction] = {
    "off": HVACAction.OFF,
    "cool": HVACAction.COOLING,
    "heat": HVACAction.HEATING,
    "dry": HVACAction.DRYING,
    "vent": HVACAction.FAN,
    "auto": HVACAction.IDLE,
    "autoCool": HVACAction.COOLING,
    "autoHeat": HVACAction.HEATING,
}

_FAN_SPEED_MAP: dict[str, FanSpeed] = {s.value: s for s in FanSpeed}
_VANE_DIR_MAP: dict[str, VaneDirection] = {d.value: d for d in VaneDirection}

_OPT_MODE = "mode"
_OPT_COOL_SETPOINT = "cool_setpoint"
_OPT_HEAT_SETPOINT = "heat_setpoint"
_OPT_FAN_SPEED = "fan_speed"
_OPT_VANE_DIRECTION = "vane_direction"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MitsubishiComfortConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Mitsubishi Comfort climate entities."""
    coordinators = entry.runtime_data
    async_add_entities(
        MitsubishiComfortClimate(coordinator)
        for coordinator in coordinators.values()
        if isinstance(coordinator.device, IndoorUnit)
    )


class MitsubishiComfortClimate(MitsubishiComfortEntity, ClimateEntity):
    """Climate entity for a Mitsubishi indoor unit."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator: MitsubishiComfortCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = self._device.serial
        self._optimistic: dict[str, Any] = {}

    def _handle_coordinator_update(self) -> None:
        """Clear optimistic state when real data arrives from device."""
        self._optimistic.clear()
        super()._handle_coordinator_update()

    @property
    def _effective_mode(self) -> str | None:
        return self._optimistic.get(_OPT_MODE, self._device.status.mode)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        mode = self._effective_mode
        return _MODE_TO_HVAC.get(mode) if mode else None

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        mode = self._effective_mode
        if mode and self._device.status.standby:
            return HVACAction.IDLE
        return _MODE_TO_ACTION.get(mode) if mode else None

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        return [
            _LIB_MODE_TO_HVAC[m]
            for m in self._device.supported_modes
            if m in _LIB_MODE_TO_HVAC
        ]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.status.room_temperature

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self._device.status.current_humidity

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        mode = self._effective_mode
        if mode in ("cool", "autoCool"):
            return self._optimistic.get(
                _OPT_COOL_SETPOINT, self._device.status.cool_setpoint
            )
        if mode in ("heat", "autoHeat"):
            return self._optimistic.get(
                _OPT_HEAT_SETPOINT, self._device.status.heat_setpoint
            )
        return None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the upper bound target temperature."""
        if self._effective_mode in ("auto", "autoCool", "autoHeat"):
            return self._optimistic.get(
                _OPT_COOL_SETPOINT, self._device.status.cool_setpoint
            )
        return None

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lower bound target temperature."""
        if self._effective_mode in ("auto", "autoCool", "autoHeat"):
            return self._optimistic.get(
                _OPT_HEAT_SETPOINT, self._device.status.heat_setpoint
            )
        return None

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        return self._optimistic.get(_OPT_FAN_SPEED, self._device.status.fan_speed)

    @property
    def fan_modes(self) -> list[str]:
        """Return the list of available fan modes."""
        return [s.value for s in self._device.supported_fan_speeds]

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        return self._optimistic.get(
            _OPT_VANE_DIRECTION, self._device.status.vane_direction
        )

    @property
    def swing_modes(self) -> list[str]:
        """Return the list of available swing modes."""
        return [d.value for d in self._device.supported_vane_directions]

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if self._effective_mode in ("heat", "autoHeat"):
            if self._device.status.min_heat_setpoint is not None:
                return self._device.status.min_heat_setpoint
        if self._device.status.min_cool_setpoint is not None:
            return self._device.status.min_cool_setpoint
        return super().min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self._effective_mode in ("heat", "autoHeat"):
            if self._device.status.max_heat_setpoint is not None:
                return self._device.status.max_heat_setpoint
        if self._device.status.max_cool_setpoint is not None:
            return self._device.status.max_cool_setpoint
        return super().max_temp

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.TURN_OFF
        )
        if Mode.AUTO in self._device.supported_modes:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        if self._device.supported_vane_directions:
            features |= ClimateEntityFeature.SWING_MODE
        return features

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        lib_mode = _HVAC_TO_MODE.get(hvac_mode)
        if lib_mode is None:
            return
        result = await self._device.set_mode(lib_mode)
        if result.success:
            self._optimistic[_OPT_MODE] = result.value
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        mode = self._effective_mode
        wrote = False

        if ATTR_TARGET_TEMP_HIGH in kwargs:
            result = await self._device.set_cool_setpoint(kwargs[ATTR_TARGET_TEMP_HIGH])
            if result.success:
                self._optimistic[_OPT_COOL_SETPOINT] = result.value
                wrote = True

        if ATTR_TARGET_TEMP_LOW in kwargs:
            result = await self._device.set_heat_setpoint(kwargs[ATTR_TARGET_TEMP_LOW])
            if result.success:
                self._optimistic[_OPT_HEAT_SETPOINT] = result.value
                wrote = True

        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            if mode in ("cool", "autoCool"):
                result = await self._device.set_cool_setpoint(temp)
                if result.success:
                    self._optimistic[_OPT_COOL_SETPOINT] = result.value
                    wrote = True
            elif mode in ("heat", "autoHeat"):
                result = await self._device.set_heat_setpoint(temp)
                if result.success:
                    self._optimistic[_OPT_HEAT_SETPOINT] = result.value
                    wrote = True

        if wrote:
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        speed = _FAN_SPEED_MAP.get(fan_mode)
        if speed is None:
            return
        result = await self._device.set_fan_speed(speed)
        if result.success:
            self._optimistic[_OPT_FAN_SPEED] = result.value
            self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode."""
        direction = _VANE_DIR_MAP.get(swing_mode)
        if direction is None:
            return
        result = await self._device.set_vane_direction(direction)
        if result.success:
            self._optimistic[_OPT_VANE_DIRECTION] = result.value
            self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
