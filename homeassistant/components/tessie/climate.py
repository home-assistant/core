"""Climate platform for Tessie integration."""

from __future__ import annotations

from itertools import chain
from typing import Any

from tessie_api import (
    set_climate_keeper_mode,
    set_temperature,
    start_cabin_overheat_protection,
    start_climate_preconditioning,
    stop_cabin_overheat_protection,
    stop_climate,
)

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_HALVES,
    PRECISION_WHOLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TessieConfigEntry
from .const import DOMAIN, TessieClimateKeeper
from .entity import TessieEntity
from .models import TessieVehicleData

PARALLEL_UPDATES = 0

COP_MODES = {"Off": HVACMode.OFF, "On": HVACMode.COOL, "FanOnly": HVACMode.FAN_ONLY}
COP_LEVELS = {"Low": 30, "Medium": 35, "High": 40}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TessieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tessie Climate platform from a config entry."""
    data = entry.runtime_data

    async_add_entities(
        chain(
            (TessieClimateEntity(vehicle) for vehicle in data.vehicles),
            (
                TessieCabinOverheatProtectionClimateEntity(vehicle)
                for vehicle in data.vehicles
            ),
        )
    )


class TessieClimateEntity(TessieEntity, ClimateEntity):
    """Vehicle Location Climate Class."""

    _attr_precision = PRECISION_HALVES
    _attr_min_temp = 15
    _attr_max_temp = 28
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT_COOL, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_preset_modes: list = [
        TessieClimateKeeper.OFF,
        TessieClimateKeeper.ON,
        TessieClimateKeeper.DOG,
        TessieClimateKeeper.CAMP,
    ]

    def __init__(
        self,
        vehicle: TessieVehicleData,
    ) -> None:
        """Initialize the Climate entity."""
        super().__init__(vehicle, "primary")

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return hvac operation ie. heat, cool mode."""
        if self.get("climate_state_is_climate_on"):
            return HVACMode.HEAT_COOL
        return HVACMode.OFF

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.get("climate_state_inside_temp")

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.get("climate_state_driver_temp_setting")

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.get("climate_state_max_avail_temp", self._attr_max_temp)

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.get("climate_state_min_avail_temp", self._attr_min_temp)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self.get("climate_state_climate_keeper_mode")

    async def async_turn_on(self) -> None:
        """Set the climate state to on."""
        await self.run(start_climate_preconditioning)
        self.set(("climate_state_is_climate_on", True))

    async def async_turn_off(self) -> None:
        """Set the climate state to off."""
        await self.run(stop_climate)
        self.set(
            ("climate_state_is_climate_on", False),
            ("climate_state_climate_keeper_mode", "off"),
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the climate temperature."""
        if mode := kwargs.get(ATTR_HVAC_MODE):
            await self.async_set_hvac_mode(mode)

        if temp := kwargs.get(ATTR_TEMPERATURE):
            await self.run(set_temperature, temperature=temp)
            self.set(("climate_state_driver_temp_setting", temp))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the climate mode and state."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the climate preset mode."""
        await self.run(
            set_climate_keeper_mode, mode=self._attr_preset_modes.index(preset_mode)
        )
        self.set(
            (
                "climate_state_climate_keeper_mode",
                preset_mode,
            ),
            (
                "climate_state_is_climate_on",
                preset_mode != self._attr_preset_modes[0],
            ),
        )


class TessieCabinOverheatProtectionClimateEntity(TessieEntity, ClimateEntity):
    """Vehicle Cabin Overheat Protection."""

    _attr_precision = PRECISION_WHOLE
    _attr_target_temperature_step = 5
    _attr_min_temp = 30
    _attr_max_temp = 40
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL]
    _attr_entity_registry_enabled_default = False
    _attr_supported_features = (
        ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        vehicle: TessieVehicleData,
    ) -> None:
        """Initialize the cabin overheat protection climate entity."""
        super().__init__(vehicle, "climate_state_cabin_overheat_protection")

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current cabin overheat protection mode."""
        if (state := self._value) is None:
            return None
        return COP_MODES.get(state)

    @property
    def current_temperature(self) -> float | None:
        """Return the inside temperature."""
        return self.get("climate_state_inside_temp")

    @property
    def target_temperature(self) -> float | None:
        """Return the activation temperature."""
        if (level := self.get("climate_state_cop_activation_temperature")) is None:
            return None
        return COP_LEVELS.get(level)

    async def async_turn_on(self) -> None:
        """Set the cabin overheat protection state to on."""
        await self.async_set_hvac_mode(HVACMode.COOL)

    async def async_turn_off(self) -> None:
        """Set the cabin overheat protection state to off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the cabin overheat protection mode."""
        if hvac_mode == HVACMode.OFF:
            await self.run(stop_cabin_overheat_protection)
            self.set((self.key, "Off"))
        elif hvac_mode == HVACMode.COOL:
            await self.run(start_cabin_overheat_protection)
            self.set((self.key, "On"))
        else:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_cop_mode",
            )
