"""Climate platform for Teslemetry integration."""

from __future__ import annotations

from itertools import chain
from typing import Any, cast

from tesla_fleet_api.const import CabinOverheatProtectionTemp, Scope
from tesla_fleet_api.teslemetry import Vehicle

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    HVAC_MODES,
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
from homeassistant.helpers.restore_state import RestoreEntity

from . import TeslemetryConfigEntry
from .const import DOMAIN, TeslemetryClimateSide
from .entity import (
    TeslemetryRootEntity,
    TeslemetryVehiclePollingEntity,
    TeslemetryVehicleStreamEntity,
)
from .helpers import handle_vehicle_command
from .models import TeslemetryVehicleData

DEFAULT_MIN_TEMP = 15
DEFAULT_MAX_TEMP = 28
COP_TEMPERATURES = {
    30: CabinOverheatProtectionTemp.LOW,
    35: CabinOverheatProtectionTemp.MEDIUM,
    40: CabinOverheatProtectionTemp.HIGH,
}
PRESET_MODES = {
    "Off": "off",
    "On": "keep",
    "Dog": "dog",
    "Party": "camp",
}


PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslemetryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Teslemetry Climate platform from a config entry."""

    async_add_entities(
        chain(
            (
                TeslemetryVehiclePollingClimateEntity(
                    vehicle, TeslemetryClimateSide.DRIVER, entry.runtime_data.scopes
                )
                if vehicle.api.pre2021 or vehicle.firmware < "2024.44.25"
                else TeslemetryStreamingClimateEntity(
                    vehicle, TeslemetryClimateSide.DRIVER, entry.runtime_data.scopes
                )
                for vehicle in entry.runtime_data.vehicles
            ),
            (
                TeslemetryVehiclePollingCabinOverheatProtectionEntity(
                    vehicle, entry.runtime_data.scopes
                )
                if vehicle.api.pre2021 or vehicle.firmware < "2024.44.25"
                else TeslemetryStreamingCabinOverheatProtectionEntity(
                    vehicle, entry.runtime_data.scopes
                )
                for vehicle in entry.runtime_data.vehicles
            ),
        )
    )


class TeslemetryClimateEntity(TeslemetryRootEntity, ClimateEntity):
    """Vehicle Climate Control."""

    api: Vehicle
    _attr_precision = PRECISION_HALVES
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT_COOL, HVACMode.OFF]
    _attr_preset_modes = list(PRESET_MODES.values())
    _attr_fan_modes = ["off", "bioweapon"]
    _enable_turn_on_off_backwards_compatibility = False

    async def async_turn_on(self) -> None:
        """Set the climate state to on."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)

        await handle_vehicle_command(self.api.auto_conditioning_start())

        self._attr_hvac_mode = HVACMode.HEAT_COOL
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Set the climate state to off."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)

        await handle_vehicle_command(self.api.auto_conditioning_stop())

        self._attr_hvac_mode = HVACMode.OFF
        self._attr_preset_mode = self._attr_preset_modes[0]
        self._attr_fan_mode = self._attr_fan_modes[0]
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the climate temperature."""

        if temp := kwargs.get(ATTR_TEMPERATURE):
            self.raise_for_scope(Scope.VEHICLE_CMDS)

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
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the climate preset mode."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)

        await handle_vehicle_command(
            self.api.set_climate_keeper_mode(
                climate_keeper_mode=self._attr_preset_modes.index(preset_mode)
            )
        )
        self._attr_preset_mode = preset_mode
        if preset_mode == self._attr_preset_modes[0]:
            self._attr_hvac_mode = HVACMode.OFF
        else:
            self._attr_hvac_mode = HVACMode.HEAT_COOL
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the Bioweapon defense mode."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)

        await handle_vehicle_command(
            self.api.set_bioweapon_mode(
                on=(fan_mode != "off"),
                manual_override=True,
            )
        )
        self._attr_fan_mode = fan_mode
        if fan_mode == self._attr_fan_modes[1]:
            self._attr_hvac_mode = HVACMode.HEAT_COOL
        self.async_write_ha_state()


class TeslemetryVehiclePollingClimateEntity(
    TeslemetryClimateEntity, TeslemetryVehiclePollingEntity
):
    """Polling vehicle climate entity."""

    _attr_supported_features = (
        ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.FAN_MODE
    )

    def __init__(
        self,
        data: TeslemetryVehicleData,
        side: TeslemetryClimateSide,
        scopes: list[Scope],
    ) -> None:
        """Initialize the climate."""
        self.scoped = Scope.VEHICLE_CMDS in scopes
        if not self.scoped:
            self._attr_supported_features = ClimateEntityFeature(0)

        super().__init__(data, side)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""
        value = self.get("climate_state_is_climate_on")
        if value is None:
            self._attr_hvac_mode = None
        if value:
            self._attr_hvac_mode = HVACMode.HEAT_COOL
        else:
            self._attr_hvac_mode = HVACMode.OFF

        self._attr_current_temperature = self.get("climate_state_inside_temp")
        self._attr_target_temperature = self.get(f"climate_state_{self.key}_setting")
        self._attr_preset_mode = self.get("climate_state_climate_keeper_mode")
        if self.get("climate_state_bioweapon_mode"):
            self._attr_fan_mode = "bioweapon"
        else:
            self._attr_fan_mode = "off"
        self._attr_min_temp = cast(
            float, self.get("climate_state_min_avail_temp", DEFAULT_MIN_TEMP)
        )
        self._attr_max_temp = cast(
            float, self.get("climate_state_max_avail_temp", DEFAULT_MAX_TEMP)
        )


class TeslemetryStreamingClimateEntity(
    TeslemetryClimateEntity, TeslemetryVehicleStreamEntity, RestoreEntity
):
    """Teslemetry steering wheel climate control."""

    _attr_supported_features = (
        ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(
        self,
        data: TeslemetryVehicleData,
        side: TeslemetryClimateSide,
        scopes: list[Scope],
    ) -> None:
        """Initialize the climate."""

        # Initialize defaults
        self._attr_hvac_mode = None
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_fan_mode = None
        self._attr_preset_mode = None

        self.scoped = Scope.VEHICLE_CMDS in scopes
        if not self.scoped:
            self._attr_supported_features = ClimateEntityFeature(0)
        self.side = side
        super().__init__(
            data,
            side,
        )

        self._attr_min_temp = cast(
            float,
            data.coordinator.data.get("climate_state_min_avail_temp", DEFAULT_MIN_TEMP),
        )
        self._attr_max_temp = cast(
            float,
            data.coordinator.data.get("climate_state_max_avail_temp", DEFAULT_MAX_TEMP),
        )
        self.rhd: bool = data.coordinator.data.get("vehicle_config_rhd", False)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            self._attr_hvac_mode = (
                HVACMode(state.state) if state.state in HVAC_MODES else None
            )
            self._attr_current_temperature = state.attributes.get("current_temperature")
            self._attr_target_temperature = state.attributes.get("temperature")
            self._attr_preset_mode = state.attributes.get("preset_mode")

        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_InsideTemp(
                self._async_handle_inside_temp
            )
        )
        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_HvacACEnabled(
                self._async_handle_hvac_ac_enabled
            )
        )
        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_ClimateKeeperMode(
                self._async_handle_climate_keeper_mode
            )
        )
        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_RightHandDrive(self._async_handle_rhd)
        )

        if self.side == TeslemetryClimateSide.DRIVER:
            if self.rhd:
                self.async_on_remove(
                    self.vehicle.stream_vehicle.listen_HvacRightTemperatureRequest(
                        self._async_handle_hvac_temperature_request
                    )
                )
            else:
                self.async_on_remove(
                    self.vehicle.stream_vehicle.listen_HvacLeftTemperatureRequest(
                        self._async_handle_hvac_temperature_request
                    )
                )
        elif self.side == TeslemetryClimateSide.PASSENGER:
            if self.rhd:
                self.async_on_remove(
                    self.vehicle.stream_vehicle.listen_HvacLeftTemperatureRequest(
                        self._async_handle_hvac_temperature_request
                    )
                )
            else:
                self.async_on_remove(
                    self.vehicle.stream_vehicle.listen_HvacRightTemperatureRequest(
                        self._async_handle_hvac_temperature_request
                    )
                )

    def _async_handle_inside_temp(self, data: float | None):
        self._attr_current_temperature = data
        self.async_write_ha_state()

    def _async_handle_hvac_ac_enabled(self, data: bool | None):
        self._attr_hvac_mode = (
            None if data is None else HVACMode.HEAT_COOL if data else HVACMode.OFF
        )
        self.async_write_ha_state()

    def _async_handle_climate_keeper_mode(self, data: str | None):
        self._attr_preset_mode = PRESET_MODES.get(data) if data else None
        self.async_write_ha_state()

    def _async_handle_hvac_temperature_request(self, data: float | None):
        self._attr_target_temperature = data
        self.async_write_ha_state()

    def _async_handle_rhd(self, data: bool | None):
        if data is not None:
            self.rhd = data


COP_MODES = {
    "Off": HVACMode.OFF,
    "On": HVACMode.COOL,
    "FanOnly": HVACMode.FAN_ONLY,
}

COP_LEVELS = {
    "Low": 30,
    "Medium": 35,
    "High": 40,
}


class TeslemetryCabinOverheatProtectionEntity(TeslemetryRootEntity, ClimateEntity):
    """Vehicle Cabin Overheat Protection."""

    api: Vehicle
    _attr_precision = PRECISION_WHOLE
    _attr_target_temperature_step = 5
    _attr_min_temp = 30
    _attr_max_temp = 40
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = list(COP_MODES.values())
    _attr_entity_registry_enabled_default = False

    _enable_turn_on_off_backwards_compatibility = False

    async def async_turn_on(self) -> None:
        """Set the climate state to on."""
        await self.async_set_hvac_mode(HVACMode.COOL)

    async def async_turn_off(self) -> None:
        """Set the climate state to off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the climate temperature."""

        if temp := kwargs.get(ATTR_TEMPERATURE):
            if (cop_mode := COP_TEMPERATURES.get(temp)) is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_cop_temp",
                )
            self.raise_for_scope(Scope.VEHICLE_CMDS)

            await handle_vehicle_command(self.api.set_cop_temp(cop_mode))
            self._attr_target_temperature = temp

        if mode := kwargs.get(ATTR_HVAC_MODE):
            # Set HVAC mode will call write_ha_state
            await self.async_set_hvac_mode(mode)
        else:
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the climate mode and state."""
        self.raise_for_scope(Scope.VEHICLE_CMDS)

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
        self.async_write_ha_state()


class TeslemetryVehiclePollingCabinOverheatProtectionEntity(
    TeslemetryVehiclePollingEntity, TeslemetryCabinOverheatProtectionEntity
):
    """Vehicle Cabin Overheat Protection."""

    def __init__(
        self,
        data: TeslemetryVehicleData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the climate."""

        super().__init__(
            data,
            "climate_state_cabin_overheat_protection",
        )

        # Supported Features
        self._attr_supported_features = (
            ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        )
        if self.get("vehicle_config_cop_user_set_temp_supported"):
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

        # Scopes
        self.scoped = Scope.VEHICLE_CMDS in scopes
        if not self.scoped:
            self._attr_supported_features = ClimateEntityFeature(0)

    def _async_update_attrs(self) -> None:
        """Update the attributes of the entity."""

        if (state := self.get("climate_state_cabin_overheat_protection")) is None:
            self._attr_hvac_mode = None
        else:
            self._attr_hvac_mode = COP_MODES.get(state)

        if (level := self.get("climate_state_cop_activation_temperature")) is None:
            self._attr_target_temperature = None
        else:
            self._attr_target_temperature = COP_LEVELS.get(level)

        self._attr_current_temperature = self.get("climate_state_inside_temp")


class TeslemetryStreamingCabinOverheatProtectionEntity(
    TeslemetryVehicleStreamEntity,
    TeslemetryCabinOverheatProtectionEntity,
    RestoreEntity,
):
    """Vehicle Cabin Overheat Protection."""

    def __init__(
        self,
        data: TeslemetryVehicleData,
        scopes: list[Scope],
    ) -> None:
        """Initialize the climate."""

        # Initialize defaults
        self._attr_hvac_mode = None
        self._attr_current_temperature = None
        self._attr_target_temperature = None
        self._attr_fan_mode = None
        self._attr_preset_mode = None

        super().__init__(data, "climate_state_cabin_overheat_protection")

        # Supported Features
        self._attr_supported_features = (
            ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        )
        if data.coordinator.data.get("vehicle_config_cop_user_set_temp_supported"):
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

        # Scopes
        self.scoped = Scope.VEHICLE_CMDS in scopes
        if not self.scoped:
            self._attr_supported_features = ClimateEntityFeature(0)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is not None:
            self._attr_hvac_mode = (
                HVACMode(state.state) if state.state in HVAC_MODES else None
            )
            self._attr_current_temperature = state.attributes.get("temperature")
            self._attr_target_temperature = state.attributes.get("target_temperature")

        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_InsideTemp(
                self._async_handle_inside_temp
            )
        )
        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_CabinOverheatProtectionMode(
                self._async_handle_protection_mode
            )
        )
        self.async_on_remove(
            self.vehicle.stream_vehicle.listen_CabinOverheatProtectionTemperatureLimit(
                self._async_handle_temperature_limit
            )
        )

    def _async_handle_inside_temp(self, value: float | None):
        self._attr_current_temperature = value
        self.async_write_ha_state()

    def _async_handle_protection_mode(self, value: str | None):
        self._attr_hvac_mode = COP_MODES.get(value) if value is not None else None
        self.async_write_ha_state()

    def _async_handle_temperature_limit(self, value: str | None):
        self._attr_target_temperature = (
            COP_LEVELS.get(value) if value is not None else None
        )
        self.async_write_ha_state()
