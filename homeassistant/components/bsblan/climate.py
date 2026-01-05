"""BSBLAN platform to control a compatible Climate Device."""

from __future__ import annotations

from typing import Any, Final

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
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.enum import try_parse_enum

from . import BSBLanConfigEntry, BSBLanData
from .const import ATTR_TARGET_TEMPERATURE, DOMAIN
from .entity import BSBLanEntity

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

# Mapping from Home Assistant HVACMode to BSB-Lan integer values
# BSB-Lan uses: 0=off, 1=auto, 2=eco/reduced, 3=heat/comfort
HA_TO_BSBLAN_HVAC_MODE: Final[dict[HVACMode, int]] = {
    HVACMode.OFF: 0,
    HVACMode.AUTO: 1,
    HVACMode.HEAT: 3,
}

# Mapping from BSB-Lan integer values to Home Assistant HVACMode
BSBLAN_TO_HA_HVAC_MODE: Final[dict[int, HVACMode]] = {
    0: HVACMode.OFF,
    1: HVACMode.AUTO,
    2: HVACMode.AUTO,  # eco/reduced maps to AUTO with preset
    3: HVACMode.HEAT,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BSBLanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BSBLAN device based on a config entry."""
    data = entry.runtime_data
    async_add_entities([BSBLANClimate(data)])


class BSBLANClimate(BSBLanEntity, ClimateEntity):
    """Defines a BSBLAN climate device."""

    _attr_has_entity_name = True
    _attr_name = None
    # Determine preset modes
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    _attr_preset_modes = PRESET_MODES
    _attr_hvac_modes = HVAC_MODES

    def __init__(
        self,
        data: BSBLanData,
    ) -> None:
        """Initialize BSBLAN climate device."""
        super().__init__(data.fast_coordinator, data)
        self._attr_unique_id = f"{format_mac(data.device.MAC)}-climate"

        # Set temperature range if available, otherwise use Home Assistant defaults
        if data.static.min_temp is not None and data.static.min_temp.value is not None:
            self._attr_min_temp = data.static.min_temp.value
        if data.static.max_temp is not None and data.static.max_temp.value is not None:
            self._attr_max_temp = data.static.max_temp.value
        self._attr_temperature_unit = data.fast_coordinator.client.get_temperature_unit

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.coordinator.data.state.current_temperature is None:
            return None
        return self.coordinator.data.state.current_temperature.value

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.coordinator.data.state.target_temperature is None:
            return None
        return self.coordinator.data.state.target_temperature.value

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        hvac_mode_value = self.coordinator.data.state.hvac_mode.value
        if hvac_mode_value is None:
            return None
        # BSB-Lan returns integer values: 0=off, 1=auto, 2=eco, 3=heat
        if isinstance(hvac_mode_value, int):
            return BSBLAN_TO_HA_HVAC_MODE.get(hvac_mode_value)
        return try_parse_enum(HVACMode, hvac_mode_value)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        hvac_mode_value = self.coordinator.data.state.hvac_mode.value
        # BSB-Lan mode 2 is eco/reduced mode
        if hvac_mode_value == 2:
            return PRESET_ECO
        return PRESET_NONE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        await self.async_set_data(hvac_mode=hvac_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        await self.async_set_data(preset_mode=preset_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        await self.async_set_data(**kwargs)

    async def async_set_data(self, **kwargs: Any) -> None:
        """Set device settings using BSBLAN."""
        data: dict[str, Any] = {}
        if ATTR_TEMPERATURE in kwargs:
            data[ATTR_TARGET_TEMPERATURE] = kwargs[ATTR_TEMPERATURE]
        if ATTR_HVAC_MODE in kwargs:
            data[ATTR_HVAC_MODE] = HA_TO_BSBLAN_HVAC_MODE[kwargs[ATTR_HVAC_MODE]]
        if ATTR_PRESET_MODE in kwargs:
            # eco preset uses BSB-Lan mode 2, none preset uses mode 1 (auto)
            if kwargs[ATTR_PRESET_MODE] == PRESET_ECO:
                data[ATTR_HVAC_MODE] = 2
            elif kwargs[ATTR_PRESET_MODE] == PRESET_NONE:
                data[ATTR_HVAC_MODE] = 1

        try:
            await self.coordinator.client.thermostat(**data)
        except BSBLANError as err:
            raise HomeAssistantError(
                "An error occurred while updating the BSBLAN device",
                translation_domain=DOMAIN,
                translation_key="set_data_error",
            ) from err
        await self.coordinator.async_request_refresh()
