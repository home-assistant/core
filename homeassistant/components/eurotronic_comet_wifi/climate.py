"""Climate platform for Comet WiFi thermostats."""

from typing import Any, override

from aiocometwifi import TEMPERATURE_SETPOINT_MAX, TEMPERATURE_SETPOINT_MIN

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CometWiFiConfigEntry
from .const import DEFAULT_SETPOINT, UNIQUE_ID_SUFFIX_CLIMATE
from .coordinator import CometWiFiDataCoordinator
from .entity import CometWiFiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CometWiFiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Comet WiFi climate platform."""
    coordinator = entry.runtime_data
    async_add_entities([CometWiFiClimateEntity(coordinator)])


class CometWiFiClimateEntity(CometWiFiEntity, ClimateEntity):
    """Climate entity for CometWiFi."""

    _attr_name = None
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features: ClimateEntityFeature = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = TEMPERATURE_SETPOINT_MIN
    _attr_max_temp = TEMPERATURE_SETPOINT_MAX
    _attr_target_temperature_step = PRECISION_HALVES

    def __init__(self, coordinator: CometWiFiDataCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac}_{UNIQUE_ID_SUFFIX_CLIMATE}"

    @property
    @override
    def current_temperature(self) -> float:
        """Returns current ambient temperature."""
        return self.coordinator.data.temperature_ambient

    @property
    @override
    def target_temperature(self) -> float:
        """Returns the current target temperature."""
        return self.coordinator.data.temperature_setpoint

    @property
    @override
    def hvac_mode(self) -> HVACMode:
        """Returns the current HVACMode."""
        if self.coordinator.data.is_heating:
            return HVACMode.HEAT
        return HVACMode.OFF

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature, unless also asked to turn off."""
        hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode is not None:
            self._valid_mode_or_raise("hvac", hvac_mode, self.hvac_modes)
        if hvac_mode == HVACMode.OFF:
            await self.async_set_hvac_mode(HVACMode.OFF)
            return
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            await self.coordinator.client.set_setpoint_temperature(temperature)
            # Keep temperature when reset within debounce window
            self.coordinator.last_heating_setpoint = temperature
            await self.coordinator.async_request_refresh()

    @override
    async def async_turn_on(self) -> None:
        """Turn thermostat on."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    @override
    async def async_turn_off(self) -> None:
        """Turn thermostat off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.HEAT:
            setpoint = self.coordinator.last_heating_setpoint
            if setpoint is None:
                setpoint = DEFAULT_SETPOINT
            await self.coordinator.client.set_setpoint_temperature(setpoint)
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.client.turn_off()
        await self.coordinator.async_request_refresh()
