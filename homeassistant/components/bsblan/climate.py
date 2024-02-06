"""BSBLAN platform to control a compatible Climate Device."""
from __future__ import annotations

from typing import Any

from bsblan import BSBLAN, BSBLANError, Device, Info, State, StaticState

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
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util.enum import try_parse_enum

from . import HomeAssistantBSBLANData
from .const import ATTR_TARGET_TEMPERATURE, DOMAIN, LOGGER
from .entity import BSBLANEntity

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
    data: HomeAssistantBSBLANData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            BSBLANClimate(
                data.coordinator,
                data.client,
                data.device,
                data.info,
                data.static,
                entry,
            )
        ]
    )


class BSBLANClimate(
    BSBLANEntity, CoordinatorEntity[DataUpdateCoordinator[State]], ClimateEntity
):
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

    # Determine hvac modes
    _attr_hvac_modes = HVAC_MODES
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[State],
        client: BSBLAN,
        device: Device,
        info: Info,
        static: StaticState,
        entry: ConfigEntry,
    ) -> None:
        """Initialize BSBLAN climate device."""
        super().__init__(client, device, info, static, entry)
        CoordinatorEntity.__init__(self, coordinator)
        self._attr_unique_id = f"{format_mac(device.MAC)}-climate"

        self._attr_min_temp = float(static.min_temp.value)
        self._attr_max_temp = float(static.max_temp.value)
        # check if self.coordinator.data.current_temperature.unit is "&deg;C" or "°C"
        if self.coordinator.data.current_temperature.unit in ("&deg;C", "°C"):
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        else:
            self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if self.coordinator.data.current_temperature.value == "---":
            # device returns no current temperature
            return None

        return float(self.coordinator.data.current_temperature.value)

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return float(self.coordinator.data.target_temperature.value)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        if self.coordinator.data.hvac_mode.value == PRESET_ECO:
            return HVACMode.AUTO
        return try_parse_enum(HVACMode, self.coordinator.data.hvac_mode.value)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if (
            self.hvac_mode == HVACMode.AUTO
            and self.coordinator.data.hvac_mode.value == PRESET_ECO
        ):
            return PRESET_ECO
        return PRESET_NONE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        await self.async_set_data(hvac_mode=hvac_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        # only allow preset mode when hvac mode is auto
        if self.hvac_mode == HVACMode.AUTO:
            await self.async_set_data(preset_mode=preset_mode)
        else:
            LOGGER.error("Can't set preset mode when hvac mode is not auto")

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
            # If preset mode is None, set hvac to auto
            if kwargs[ATTR_PRESET_MODE] == PRESET_NONE:
                data[ATTR_HVAC_MODE] = HVACMode.AUTO
            else:
                data[ATTR_HVAC_MODE] = kwargs[ATTR_PRESET_MODE]
        try:
            await self.client.thermostat(**data)
        except BSBLANError:
            LOGGER.error("An error occurred while updating the BSBLAN device")
        await self.coordinator.async_request_refresh()
