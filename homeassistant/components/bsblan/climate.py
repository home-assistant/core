"""BSBLAN platform to control a compatible Climate Device."""

from __future__ import annotations

from typing import Any

from bsblan import BSBLANError

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_TARGET_TEMPERATURE, DOMAIN
from .entity import BSBLanEntity
from .models import BSBLanData

PARALLEL_UPDATES = 1

HVAC_MODES = [
    HVACMode.AUTO,
    HVACMode.HEAT,
    HVACMode.OFF,
]

PRESET_MODES = [
    PRESET_ECO,
    PRESET_NONE,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BSBLAN device based on a config entry."""
    data: BSBLanData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BSBLANClimate(data)])


class BSBLANClimate(BSBLanEntity, ClimateEntity):
    """Defines a BSBLAN climate device."""

    _attr_has_entity_name = True
    _attr_name: str | None = None
    _attr_translation_key = "Thermostat"
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_preset_modes = PRESET_MODES
    _attr_hvac_modes = HVAC_MODES
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, data: BSBLanData) -> None:
        """Initialize BSBLAN climate device."""
        super().__init__(data.coordinator, data)
        self._attr_unique_id = f"{self._data.device.MAC}-climate"
        self._attr_name = self._attr_translation_key
        self._attr_min_temp = float(self._data.static.min_temp.value)
        self._attr_max_temp = float(self._data.static.max_temp.value)
        self._attr_temperature_unit = self.temperature_unit

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return (
            UnitOfTemperature.CELSIUS
            if self._data.static.min_temp.unit in ("&deg;C", "°C")
            else UnitOfTemperature.FAHRENHEIT
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        state = self.coordinator.data.state
        return (
            float(state.current_temperature.value)
            if state.current_temperature.value != "---"
            else None
        )

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return float(self.coordinator.data.state.target_temperature.value)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        state = self.coordinator.data.state
        return (
            HVACMode.AUTO
            if state.hvac_mode.value == PRESET_ECO
            else HVACMode(state.hvac_mode.value)
        )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        state = self.coordinator.data.state
        return (
            PRESET_ECO
            if self.hvac_mode == HVACMode.AUTO and state.hvac_mode.value == PRESET_ECO
            else PRESET_NONE
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        await self.async_set_data(hvac_mode=hvac_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if self.hvac_mode != HVACMode.AUTO:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="set_preset_mode_error",
                translation_placeholders={"preset_mode": preset_mode},
            )
        await self.async_set_data(preset_mode=preset_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        await self.async_set_data(**kwargs)

    async def async_set_data(self, **kwargs: Any) -> None:
        """Set device settings using BSBLAN."""
        data = {}
        if ATTR_TEMPERATURE in kwargs:
            data[ATTR_TARGET_TEMPERATURE] = kwargs[ATTR_TEMPERATURE]
        if ATTR_HVAC_MODE in kwargs:
            data[ATTR_HVAC_MODE] = kwargs[ATTR_HVAC_MODE]
        if ATTR_PRESET_MODE in kwargs:
            if kwargs[ATTR_PRESET_MODE] == PRESET_ECO:
                data[ATTR_HVAC_MODE] = PRESET_ECO
            elif kwargs[ATTR_PRESET_MODE] == PRESET_NONE:
                data[ATTR_HVAC_MODE] = HVACMode.AUTO

        try:
            await self._data.client.thermostat(**data)
        except BSBLANError as err:
            raise HomeAssistantError(
                "An error occurred while updating the BSBLAN device",
                translation_domain=DOMAIN,
                translation_key="set_data_error",
            ) from err
        await self.coordinator.async_request_refresh()
