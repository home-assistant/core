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
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
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

# Parameter 8000 ("Status heating circuit 1") and related BSB-Lan ENUM
# tables (notably 8004, 8005, 8006 and 8010) yield vendor specific status
# codes. These sets capture the most common codes we need for Home Assistant's
# simplified HVAC action states. Any unmapped code will fall back to IDLE.
BSBLAN_HVAC_ACTION_HEATING: Final[set[int]] = {
    0x04,
    0x11,
    0x16,
    0x17,
    0x18,
    0x38,
    0x65,
    0x67,
    0x68,
    0x69,
    0x6A,
    0x72,
    0x73,
    0x74,
    0x75,
    0x77,
    0x78,
    0x79,
    0x7A,
    0x89,
}

BSBLAN_HVAC_ACTION_PREHEATING: Final[set[int]] = {
    0x6F,
    0x70,
    0x71,
}

BSBLAN_HVAC_ACTION_DRYING: Final[set[int]] = {
    0x66,
}

BSBLAN_HVAC_ACTION_FAN: Final[set[int]] = {
    0x6B,
    0x6C,
    0x6D,
    0x6E,
}

BSBLAN_HVAC_ACTION_COOLING: Final[set[int]] = {
    0x7F,
    0x80,
    0x81,
    0x82,
    0x83,
    0x84,
    0x85,
    0x86,
    0x88,
    0x90,
    0x91,
    0x94,
    0x95,
    0x96,
    0xB1,
    0xB2,
    0xB3,
    0x8E,
    0xC4,
    0xCF,
    0xD0,
    0xD1,
    0xD2,
    0x11D,
}

BSBLAN_HVAC_ACTION_OFF: Final[set[int]] = {
    0x02,
    0x19,
    0x76,
    0x8C,
    0x8A,
    0x92,
    0xA1,
    0xA2,
    0xCC,
    0xCD,
    0xCE,
}

BSBLAN_HVAC_ACTION_DEFROSTING: Final[set[int]] = {
    0x7D,
    0x7E,
    0x82,
    0x83,
    0xCA,
    0xC0,
    0xC1,
    0xC2,
    0xC3,
    0x101,
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
        if self.coordinator.data.state.hvac_mode.value == PRESET_ECO:
            return HVACMode.AUTO
        return try_parse_enum(HVACMode, self.coordinator.data.state.hvac_mode.value)

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac action."""
        action = self.coordinator.data.state.hvac_action
        if action is None or action.value in (None, ""):
            return None

        raw_value = action.value
        try:
            if isinstance(raw_value, str):
                value = raw_value.strip()
                if not value:
                    return None
                base = 16 if value.lower().startswith("0x") else 10
                action_code = int(value, base)
            elif isinstance(raw_value, (int, float)):
                action_code = int(raw_value)
            else:
                return None
        except (TypeError, ValueError):
            return None

        if action_code in BSBLAN_HVAC_ACTION_DEFROSTING:
            return HVACAction.DEFROSTING
        if action_code in BSBLAN_HVAC_ACTION_DRYING:
            return HVACAction.DRYING
        if action_code in BSBLAN_HVAC_ACTION_FAN:
            return HVACAction.FAN
        if action_code in BSBLAN_HVAC_ACTION_PREHEATING:
            return HVACAction.PREHEATING
        if action_code in BSBLAN_HVAC_ACTION_COOLING:
            return HVACAction.COOLING
        if action_code in BSBLAN_HVAC_ACTION_HEATING:
            return HVACAction.HEATING
        if action_code in BSBLAN_HVAC_ACTION_OFF:
            return HVACAction.OFF
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if (
            self.hvac_mode == HVACMode.AUTO
            and self.coordinator.data.state.hvac_mode.value == PRESET_ECO
        ):
            return PRESET_ECO
        return PRESET_NONE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        await self.async_set_data(hvac_mode=hvac_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if self.hvac_mode != HVACMode.AUTO and preset_mode != PRESET_NONE:
            raise ServiceValidationError(
                "Preset mode can only be set when HVAC mode is set to 'auto'",
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
                data[ATTR_HVAC_MODE] = PRESET_NONE

        try:
            await self.coordinator.client.thermostat(**data)
        except BSBLANError as err:
            raise HomeAssistantError(
                "An error occurred while updating the BSBLAN device",
                translation_domain=DOMAIN,
                translation_key="set_data_error",
            ) from err
        await self.coordinator.async_request_refresh()
