"""Climate entity for Mitsubishi Comfort Cloud integration."""

import logging
from typing import Any, NoReturn, override

from mitsubishi_comfort import (
    FanSpeed,
    Mode,
    VaneDirection,
    fahrenheit_to_setpoint,
    setpoint_to_fahrenheit,
)

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    MitsubishiComfortCloudConfigEntry,
    MitsubishiComfortCloudCoordinator,
)
from .entity import MitsubishiComfortCloudEntity

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

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
    "auto": HVACAction.IDLE,
    "autoCool": HVACAction.COOLING,
    "autoHeat": HVACAction.HEATING,
    "vent": HVACAction.FAN,
}

_FAN_SPEED_MAP: dict[str, FanSpeed] = {s.name.lower(): s for s in FanSpeed}
_FAN_SPEED_TO_MODE = {speed.value: mode for mode, speed in _FAN_SPEED_MAP.items()}
_VANE_DIR_MAP: dict[str, VaneDirection] = {d.value: d for d in VaneDirection}

_OPT_MODE = "mode"
_OPT_COOL_SETPOINT = "cool_setpoint"
_OPT_HEAT_SETPOINT = "heat_setpoint"
_OPT_FAN_SPEED = "fan_speed"
_OPT_VANE_DIRECTION = "vane_direction"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MitsubishiComfortCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Mitsubishi Comfort Cloud climate entities."""
    coordinators = entry.runtime_data
    async_add_entities(
        MitsubishiComfortCloudClimate(coordinator)
        for coordinator in coordinators.values()
    )


class MitsubishiComfortCloudClimate(MitsubishiComfortCloudEntity, ClimateEntity):
    """Climate entity for a Mitsubishi indoor unit."""

    _attr_name = None
    _attr_translation_key = "thermostat"
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator: MitsubishiComfortCloudCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = self._device.serial
        self._optimistic: dict[str, Any] = {}

    @override
    def _handle_coordinator_update(self) -> None:
        """Clear optimistic state when real data arrives from device."""
        self._optimistic.clear()
        super()._handle_coordinator_update()

    @property
    def _effective_mode(self) -> str | None:
        return self._optimistic.get(_OPT_MODE, self._device.status.mode)

    @property
    @override
    def native_temperature_unit(self) -> str:
        """Preserve Fahrenheit requests for Mitsubishi's setpoint conversion."""
        return self.hass.config.units.temperature_unit

    @property
    @override
    def target_temperature_step(self) -> float:
        """Return the app's selectable temperature step."""
        if self.native_temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return 1.0
        return 0.5

    def _native_temperature(self, temperature: float | None) -> float | None:
        """Convert device temperatures to the app's display unit."""
        if temperature is None:
            return None
        if self.native_temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return setpoint_to_fahrenheit(temperature)
        return temperature

    def _celsius_setpoint(self, temperature: float) -> float:
        """Convert a requested setpoint to the library's Celsius unit."""
        if self.native_temperature_unit == UnitOfTemperature.FAHRENHEIT:
            return fahrenheit_to_setpoint(temperature)
        return temperature

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        mode = self._effective_mode
        return _MODE_TO_HVAC.get(mode) if mode else None

    @property
    @override
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        # Use polled stages, not an optimistically selected operating mode.
        mode = self._device.status.mode
        return _MODE_TO_ACTION.get(mode) if mode else None

    @property
    @override
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        return [
            _LIB_MODE_TO_HVAC[m]
            for m in self._device.supported_modes
            if m in _LIB_MODE_TO_HVAC
        ]

    @property
    @override
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        # The cloud's roomTemp uses the same display table as its setpoints.
        return self._native_temperature(self._device.status.room_temperature)

    @property
    @override
    def current_humidity(self) -> float | None:
        """Return the current humidity."""
        return self._device.status.current_humidity

    @property
    @override
    def native_target_temperature(self) -> float | None:
        """Return the target temperature."""
        mode = self._effective_mode
        if mode == "cool":
            return self._native_temperature(
                self._optimistic.get(
                    _OPT_COOL_SETPOINT, self._device.status.cool_setpoint
                )
            )
        if mode == "heat":
            return self._native_temperature(
                self._optimistic.get(
                    _OPT_HEAT_SETPOINT, self._device.status.heat_setpoint
                )
            )
        return None

    @property
    @override
    def native_target_temperature_high(self) -> float | None:
        """Return the upper bound target temperature."""
        if self._effective_mode in ("auto", "autoCool", "autoHeat"):
            return self._native_temperature(
                self._optimistic.get(
                    _OPT_COOL_SETPOINT, self._device.status.cool_setpoint
                )
            )
        return None

    @property
    @override
    def native_target_temperature_low(self) -> float | None:
        """Return the lower bound target temperature."""
        if self._effective_mode in ("auto", "autoCool", "autoHeat"):
            return self._native_temperature(
                self._optimistic.get(
                    _OPT_HEAT_SETPOINT, self._device.status.heat_setpoint
                )
            )
        return None

    @property
    @override
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        speed = self._optimistic.get(_OPT_FAN_SPEED, self._device.status.fan_speed)
        return _FAN_SPEED_TO_MODE.get(speed) if speed else None

    @property
    @override
    def fan_modes(self) -> list[str]:
        """Return the list of available fan modes."""
        return [s.name.lower() for s in self._device.supported_fan_speeds]

    @property
    @override
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        return self._optimistic.get(
            _OPT_VANE_DIRECTION, self._device.status.vane_direction
        )

    @property
    @override
    def swing_modes(self) -> list[str]:
        """Return the list of available swing modes."""
        return [d.value for d in self._device.supported_vane_directions]

    @property
    @override
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        # Service validation runs before a requested HVAC mode change.
        return min(
            (
                setpoint_to_fahrenheit(bound)
                if self.native_temperature_unit == UnitOfTemperature.FAHRENHEIT
                else bound
                for bound in (
                    self._device.status.min_heat_setpoint,
                    self._device.status.min_cool_setpoint,
                    self._device.status.min_auto_setpoint,
                )
                if bound is not None
            ),
            default=super().min_temp,
        )

    @property
    @override
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return max(
            (
                setpoint_to_fahrenheit(bound)
                if self.native_temperature_unit == UnitOfTemperature.FAHRENHEIT
                else bound
                for bound in (
                    self._device.status.max_heat_setpoint,
                    self._device.status.max_cool_setpoint,
                    self._device.status.max_auto_setpoint,
                )
                if bound is not None
            ),
            default=super().max_temp,
        )

    @property
    @override
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_OFF
        )
        if self._device.supported_fan_speeds:
            features |= ClimateEntityFeature.FAN_MODE
        if Mode.AUTO in self._device.supported_modes:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        if self._device.supported_vane_directions:
            features |= ClimateEntityFeature.SWING_MODE
        return features

    def _command_failed(self, translation_key: str) -> NoReturn:
        """Raise a translated error after the device rejects a command."""
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"device_name": self._device.name},
        )

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        lib_mode = _HVAC_TO_MODE.get(hvac_mode)
        if lib_mode is None:
            _LOGGER.debug("Ignoring unsupported HVAC mode %s", hvac_mode)
            return
        result = await self.coordinator.async_command(self._device.set_mode(lib_mode))
        if not result.success:
            self._command_failed("set_hvac_mode_failed")
        self._optimistic[_OPT_MODE] = result.value
        self.async_write_ha_state()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        for key in (ATTR_TEMPERATURE, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW):
            if key in kwargs:
                kwargs[key] = self._celsius_setpoint(kwargs[key])
        if ATTR_HVAC_MODE in kwargs:
            await self.async_handle_set_hvac_mode_service(kwargs[ATTR_HVAC_MODE])
        mode = self._effective_mode
        failed = False

        # Publish accepted setpoints before a subsequent command can fail.
        if ATTR_TARGET_TEMP_HIGH in kwargs:
            result = await self.coordinator.async_command(
                self._device.set_cool_setpoint(kwargs[ATTR_TARGET_TEMP_HIGH])
            )
            if result.success:
                self._optimistic[_OPT_COOL_SETPOINT] = result.value
                self.async_write_ha_state()
            else:
                failed = True

        if ATTR_TARGET_TEMP_LOW in kwargs:
            result = await self.coordinator.async_command(
                self._device.set_heat_setpoint(kwargs[ATTR_TARGET_TEMP_LOW])
            )
            if result.success:
                self._optimistic[_OPT_HEAT_SETPOINT] = result.value
                self.async_write_ha_state()
            else:
                failed = True

        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            if mode in ("cool", "autoCool"):
                result = await self.coordinator.async_command(
                    self._device.set_cool_setpoint(temp)
                )
                if result.success:
                    self._optimistic[_OPT_COOL_SETPOINT] = result.value
                    self.async_write_ha_state()
                else:
                    failed = True
            elif mode in ("heat", "autoHeat"):
                result = await self.coordinator.async_command(
                    self._device.set_heat_setpoint(temp)
                )
                if result.success:
                    self._optimistic[_OPT_HEAT_SETPOINT] = result.value
                    self.async_write_ha_state()
                else:
                    failed = True
            else:
                _LOGGER.debug(
                    "Ignoring temperature for %s: no setpoint applies in mode %s",
                    self._device.name,
                    mode,
                )

        if failed:
            self._command_failed("set_temperature_failed")

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        speed = _FAN_SPEED_MAP.get(fan_mode)
        if speed is None:
            _LOGGER.debug("Ignoring unsupported fan mode %s", fan_mode)
            return
        result = await self.coordinator.async_command(self._device.set_fan_speed(speed))
        if not result.success:
            self._command_failed("set_fan_mode_failed")
        self._optimistic[_OPT_FAN_SPEED] = result.value
        self.async_write_ha_state()

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode."""
        direction = _VANE_DIR_MAP.get(swing_mode)
        if direction is None:
            _LOGGER.debug("Ignoring unsupported swing mode %s", swing_mode)
            return
        result = await self.coordinator.async_command(
            self._device.set_vane_direction(direction)
        )
        if not result.success:
            self._command_failed("set_swing_mode_failed")
        self._optimistic[_OPT_VANE_DIRECTION] = result.value
        self.async_write_ha_state()

    @override
    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
