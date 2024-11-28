"""Climate platform for Tesla Fleet integration."""

from __future__ import annotations

from itertools import chain
from typing import Any, cast

from tesla_fleet_api.const import CabinOverheatProtectionTemp, Scope

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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TeslaFleetConfigEntry
from .const import DOMAIN, TeslaFleetClimateSide
from .entity import TeslaFleetVehicleEntity
from .helpers import handle_vehicle_command
from .models import TeslaFleetVehicleData

DEFAULT_MIN_TEMP = 15
DEFAULT_MAX_TEMP = 28

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslaFleetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tesla Fleet Climate platform from a config entry."""

    async_add_entities(
        chain(
            (
                TeslaFleetClimateEntity(
                    vehicle, TeslaFleetClimateSide.DRIVER, entry.runtime_data.scopes
                )
                for vehicle in entry.runtime_data.vehicles
            ),
            (
                TeslaFleetCabinOverheatProtectionEntity(
                    vehicle, entry.runtime_data.scopes
                )
                for vehicle in entry.runtime_data.vehicles
            ),
        )
    )


class TeslaFleetClimateEntity(TeslaFleetVehicleEntity, ClimateEntity):
    """Tesla Fleet vehicle climate entity."""

    _attr_precision = PRECISION_HALVES

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT_COOL, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = ["off", "keep", "dog", "camp"]
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        data: TeslaFleetVehicleData,
        side: TeslaFleetClimateSide,
        scopes: Scope,
    ) -> None:
        """Initialize the climate."""

        self.read_only = Scope.VEHICLE_CMDS not in scopes

        if self.read_only:
            self._attr_supported_features = ClimateEntityFeature(0)
            self._attr_hvac_modes = []

        super().__init__(
            data,
            side,
        )

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        value = self.get("climate_state_is_climate_on")
        if value is None:
            self._attr_hvac_mode = None
        elif value:
            self._attr_hvac_mode = HVACMode.HEAT_COOL
        else:
            self._attr_hvac_mode = HVACMode.OFF

        # If not scoped, prevent the user from changing the HVAC mode by making it the only option
        if self._attr_hvac_mode and self.read_only:
            self._attr_hvac_modes = [self._attr_hvac_mode]

        self._attr_current_temperature = self.get("climate_state_inside_temp")
        self._attr_target_temperature = self.get(f"climate_state_{self.key}_setting")
        self._attr_preset_mode = self.get("climate_state_climate_keeper_mode")
        self._attr_min_temp = cast(
            float, self.get("climate_state_min_avail_temp", DEFAULT_MIN_TEMP)
        )
        self._attr_max_temp = cast(
            float, self.get("climate_state_max_avail_temp", DEFAULT_MAX_TEMP)
        )

    async def async_turn_on(self) -> None:
        """Set the climate state to on."""

        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.auto_conditioning_start())

        self._attr_hvac_mode = HVACMode.HEAT_COOL
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Set the climate state to off."""

        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.auto_conditioning_stop())

        self._attr_hvac_mode = HVACMode.OFF
        self._attr_preset_mode = self._attr_preset_modes[0]
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the climate temperature."""

        if ATTR_TEMPERATURE not in kwargs:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="missing_temperature",
            )

        temp = kwargs[ATTR_TEMPERATURE]
        await self.wake_up_if_asleep()
        await handle_vehicle_command(
            self.api.set_temps(
                driver_temp=temp,
                passenger_temp=temp,
            )
        )
        self._attr_target_temperature = temp

        if mode := kwargs.get(ATTR_HVAC_MODE):
            # Set HVAC mode will call write_ha_state
            await self.async_set_hvac_mode(mode)
        else:
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the climate mode and state."""
        if hvac_mode not in self.hvac_modes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_hvac_mode",
                translation_placeholders={"hvac_mode": hvac_mode},
            )
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the climate preset mode."""
        await self.wake_up_if_asleep()
        await handle_vehicle_command(
            self.api.set_climate_keeper_mode(
                climate_keeper_mode=self._attr_preset_modes.index(preset_mode)
            )
        )
        self._attr_preset_mode = preset_mode
        if preset_mode != self._attr_preset_modes[0]:
            self._attr_hvac_mode = HVACMode.HEAT_COOL
        self.async_write_ha_state()


COP_MODES = {
    "Off": HVACMode.OFF,
    "On": HVACMode.COOL,
    "FanOnly": HVACMode.FAN_ONLY,
}

# String to celsius
COP_LEVELS = {
    "Low": 30,
    "Medium": 35,
    "High": 40,
}

# Celsius to IntEnum
TEMP_LEVELS = {
    30: CabinOverheatProtectionTemp.LOW,
    35: CabinOverheatProtectionTemp.MEDIUM,
    40: CabinOverheatProtectionTemp.HIGH,
}


class TeslaFleetCabinOverheatProtectionEntity(TeslaFleetVehicleEntity, ClimateEntity):
    """Tesla Fleet vehicle cabin overheat protection entity."""

    _attr_precision = PRECISION_WHOLE
    _attr_target_temperature_step = 5
    _attr_min_temp = COP_LEVELS["Low"]
    _attr_max_temp = COP_LEVELS["High"]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = list(COP_MODES.values())
    _enable_turn_on_off_backwards_compatibility = False
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        data: TeslaFleetVehicleData,
        scopes: Scope,
    ) -> None:
        """Initialize the cabin overheat climate entity."""

        # Scopes
        self.read_only = Scope.VEHICLE_CMDS not in scopes

        # Supported Features
        if self.read_only:
            self._attr_supported_features = ClimateEntityFeature(0)
            self._attr_hvac_modes = []
        else:
            self._attr_supported_features = (
                ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
            )

        super().__init__(data, "climate_state_cabin_overheat_protection")

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""

        if (state := self.get("climate_state_cabin_overheat_protection")) is None:
            self._attr_hvac_mode = None
        else:
            self._attr_hvac_mode = COP_MODES.get(state)

        # If not scoped, prevent the user from changing the HVAC mode by making it the only option
        if self._attr_hvac_mode and self.read_only:
            self._attr_hvac_modes = [self._attr_hvac_mode]

        if (level := self.get("climate_state_cop_activation_temperature")) is None:
            self._attr_target_temperature = None
        else:
            self._attr_target_temperature = COP_LEVELS.get(level)

        self._attr_current_temperature = self.get("climate_state_inside_temp")

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        if not self.read_only and self.get(
            "vehicle_config_cop_user_set_temp_supported"
        ):
            return (
                self._attr_supported_features | ClimateEntityFeature.TARGET_TEMPERATURE
            )
        return self._attr_supported_features

    async def async_turn_on(self) -> None:
        """Set the climate state to on."""
        await self.async_set_hvac_mode(HVACMode.COOL)

    async def async_turn_off(self) -> None:
        """Set the climate state to off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the climate temperature."""

        if ATTR_TEMPERATURE not in kwargs:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="missing_temperature",
            )

        temp = kwargs[ATTR_TEMPERATURE]
        if (cop_mode := TEMP_LEVELS.get(temp)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_cop_temp",
            )

        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.set_cop_temp(cop_mode))
        self._attr_target_temperature = temp

        if mode := kwargs.get(ATTR_HVAC_MODE):
            await self._async_set_cop(mode)

        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the climate mode and state."""
        await self.wake_up_if_asleep()
        await self._async_set_cop(hvac_mode)
        self.async_write_ha_state()

    async def _async_set_cop(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await handle_vehicle_command(
                self.api.set_cabin_overheat_protection(on=False, fan_only=False)
            )
        elif hvac_mode == HVACMode.COOL:
            await handle_vehicle_command(
                self.api.set_cabin_overheat_protection(on=True, fan_only=False)
            )
        elif hvac_mode == HVACMode.FAN_ONLY:
            await handle_vehicle_command(
                self.api.set_cabin_overheat_protection(on=True, fan_only=True)
            )

        self._attr_hvac_mode = hvac_mode
