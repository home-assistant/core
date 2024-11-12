"""TOLO Sauna climate controls (main sauna control)."""

from __future__ import annotations

from typing import Any

from tololib import (
    TARGET_HUMIDITY_MAX,
    TARGET_HUMIDITY_MIN,
    TARGET_TEMPERATURE_MAX,
    TARGET_TEMPERATURE_MIN,
    Calefaction,
)

from homeassistant.components.climate import (
    FAN_OFF,
    FAN_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ToloSaunaUpdateCoordinator
from .entity import ToloSaunaCoordinatorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate controls for TOLO Sauna."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SaunaClimate(coordinator, entry)])


class SaunaClimate(ToloSaunaCoordinatorEntity, ClimateEntity):
    """Sauna climate control."""

    _attr_fan_modes = [FAN_ON, FAN_OFF]
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.DRY]
    _attr_max_humidity = TARGET_HUMIDITY_MAX
    _attr_max_temp = TARGET_TEMPERATURE_MAX
    _attr_min_humidity = TARGET_HUMIDITY_MIN
    _attr_min_temp = TARGET_TEMPERATURE_MIN
    _attr_name = None
    _attr_precision = PRECISION_WHOLE
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_HUMIDITY
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = 1
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self, coordinator: ToloSaunaUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize TOLO Sauna Climate entity."""
        super().__init__(coordinator, entry)

        self._attr_unique_id = f"{entry.entry_id}_climate"

    @property
    def current_temperature(self) -> int:
        """Return current temperature."""
        return self.coordinator.data.status.current_temperature

    @property
    def current_humidity(self) -> int:
        """Return current humidity."""
        return self.coordinator.data.status.current_humidity

    @property
    def target_temperature(self) -> int:
        """Return target temperature."""
        return self.coordinator.data.settings.target_temperature

    @property
    def target_humidity(self) -> int:
        """Return target humidity."""
        return self.coordinator.data.settings.target_humidity

    @property
    def hvac_mode(self) -> HVACMode:
        """Get current HVAC mode."""
        if self.coordinator.data.status.power_on:
            return HVACMode.HEAT
        if (
            not self.coordinator.data.status.power_on
            and self.coordinator.data.status.fan_on
        ):
            return HVACMode.DRY
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Execute HVAC action."""
        if self.coordinator.data.status.calefaction == Calefaction.HEAT:
            return HVACAction.HEATING
        if self.coordinator.data.status.calefaction == Calefaction.KEEP:
            return HVACAction.IDLE
        if self.coordinator.data.status.calefaction == Calefaction.INACTIVE:
            if self.coordinator.data.status.fan_on:
                return HVACAction.DRYING
            return HVACAction.OFF
        return None

    @property
    def fan_mode(self) -> str:
        """Return current fan mode."""
        if self.coordinator.data.status.fan_on:
            return FAN_ON
        return FAN_OFF

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            self._set_power_and_fan(False, False)
        if hvac_mode == HVACMode.HEAT:
            self._set_power_and_fan(True, False)
        if hvac_mode == HVACMode.DRY:
            self._set_power_and_fan(False, True)

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        self.coordinator.client.set_fan_on(fan_mode == FAN_ON)

    def set_humidity(self, humidity: int) -> None:
        """Set desired target humidity."""
        self.coordinator.client.set_target_humidity(humidity)

    def set_temperature(self, **kwargs: Any) -> None:
        """Set desired target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        self.coordinator.client.set_target_temperature(round(temperature))

    def _set_power_and_fan(self, power_on: bool, fan_on: bool) -> None:
        """Shortcut for setting power and fan of TOLO device on one method."""
        self.coordinator.client.set_power_on(power_on)
        self.coordinator.client.set_fan_on(fan_on)
