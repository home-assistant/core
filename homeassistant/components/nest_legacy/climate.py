"""Climate platform for Nest thermostats and heat links."""

from __future__ import annotations

from typing import Any

from bidict import bidict

from homeassistant.components.climate import (
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NestConfigEntry, NestCoordinator
from .entity import NestEntity
from .pynest.enums import ThermostatHvacMode, ThermostatHvacState
from .pynest.models import NestThermostat

PARALLEL_UPDATES = 0

_THERMOSTAT_MIN_TEMPERATURE = 9
_THERMOSTAT_MAX_TEMPERATURE = 32

_HVAC_MODE_BIDICT: bidict[ThermostatHvacMode, HVACMode] = bidict(
    {
        ThermostatHvacMode.OFF: HVACMode.OFF,
        ThermostatHvacMode.COOL: HVACMode.COOL,
        ThermostatHvacMode.HEAT: HVACMode.HEAT,
        ThermostatHvacMode.RANGE: HVACMode.HEAT_COOL,
    }
)

_HVAC_ACTION_MAP = {
    ThermostatHvacState.OFF: HVACAction.IDLE,
    ThermostatHvacState.HEATING: HVACAction.HEATING,
    ThermostatHvacState.COOLING: HVACAction.COOLING,
    ThermostatHvacState.FAN: HVACAction.FAN,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NestConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Nest climate platform from a config entry."""
    coordinator = entry.runtime_data
    entities = [
        NestClimate(coordinator, device)
        for device in coordinator.data.values()
        if isinstance(device, NestThermostat)
    ]
    async_add_devices(entities)


class NestClimate(NestEntity[NestThermostat], ClimateEntity):
    """Representation of a Nest thermostat."""

    _attr_name = None  # Main feature of the device

    def __init__(
        self,
        coordinator: NestCoordinator,
        device: NestThermostat,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, device)
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_min_temp = _THERMOSTAT_MIN_TEMPERATURE
        self._attr_max_temp = _THERMOSTAT_MAX_TEMPERATURE
        self._attr_target_temperature_step = PRECISION_HALVES

        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.PRESET_MODE
        )
        if device.has_dehumidifier or device.has_humidifier:
            features |= ClimateEntityFeature.TARGET_HUMIDITY

        self._attr_supported_features = features
        self._attr_preset_modes = [PRESET_NONE, PRESET_ECO]

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation."""
        return _HVAC_MODE_BIDICT.get(self.device.hvac_mode)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        modes = [HVACMode.OFF]
        if self.device.can_heat:
            modes.append(HVACMode.HEAT)
        if self.device.can_cool:
            modes.append(HVACMode.COOL)
        if self.device.can_heat and self.device.can_cool:
            modes.append(HVACMode.HEAT_COOL)
        return modes

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        return _HVAC_ACTION_MAP.get(self.device.hvac_state)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.device.current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return None
        return self.device.target_temperature

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound temperature."""
        return (
            self.device.target_temperature_high
            if self.hvac_mode == HVACMode.HEAT_COOL
            else None
        )

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound temperature."""
        return (
            self.device.target_temperature_low
            if self.hvac_mode == HVACMode.HEAT_COOL
            else None
        )

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self.device.current_humidity

    @property
    def target_humidity(self) -> float | None:
        """Return the target humidity."""
        return self.device.target_humidity

    @property
    def min_humidity(self) -> float:
        """Return the minimum humidity."""
        return 15

    @property
    def max_humidity(self) -> float:
        """Return the maximum humidity."""
        return 90

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp."""
        return PRESET_ECO if self.device.is_eco_mode else PRESET_NONE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        payload: dict[str, Any] = {}

        if self.device.is_eco_mode:
            payload["eco"] = {"mode": "schedule"}

        if ATTR_TEMPERATURE in kwargs:
            payload["target_temperature"] = kwargs[ATTR_TEMPERATURE]
        if "target_temp_low" in kwargs:
            payload["target_temperature_low"] = kwargs["target_temp_low"]
        if "target_temp_high" in kwargs:
            payload["target_temperature_high"] = kwargs["target_temp_high"]

        if payload:
            await self._set_device_data(payload)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        nest_mode = _HVAC_MODE_BIDICT.inverse.get(hvac_mode)
        if nest_mode:
            payload = {"hvac_mode": nest_mode.value}
            await self._set_device_data(payload)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        nest_eco_mode = "manual-eco" if preset_mode == PRESET_ECO else "schedule"
        payload = {"eco": {"mode": nest_eco_mode}}
        await self._set_device_data(payload)

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self._set_device_data({"target_humidity": humidity})
