"""Matter climate platform."""
from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types
from matter_server.common.helpers.util import create_attribute_path_from_attribute

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint

    from .discovery import MatterEntityInfo

TEMPERATURE_SCALING_FACTOR = 100
HVAC_SYSTEM_MODE_MAP = {
    HVACMode.OFF: 0,
    HVACMode.HEAT_COOL: 1,
    HVACMode.COOL: 3,
    HVACMode.HEAT: 4,
}
SystemModeEnum = clusters.Thermostat.Enums.ThermostatSystemMode
ControlSequenceEnum = clusters.Thermostat.Enums.ThermostatControlSequence
ThermostatFeature = clusters.Thermostat.Bitmaps.Feature


class ThermostatRunningState(IntEnum):
    """Thermostat Running State, Matter spec Thermostat 7.33."""

    Heat = 1  # 1 << 0 = 1
    Cool = 2  # 1 << 1 = 2
    Fan = 4  # 1 << 2 = 4
    HeatStage2 = 8  # 1 << 3 = 8
    CoolStage2 = 16  # 1 << 4 = 16
    FanStage2 = 32  # 1 << 5 = 32
    FanStage3 = 64  # 1 << 6 = 64


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter climate platform from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.CLIMATE, async_add_entities)


class MatterClimate(MatterEntity, ClimateEntity):
    """Representation of a Matter climate entity."""

    _attr_temperature_unit: str = UnitOfTemperature.CELSIUS
    _attr_hvac_mode: HVACMode = HVACMode.OFF
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        matter_client: MatterClient,
        endpoint: MatterEndpoint,
        entity_info: MatterEntityInfo,
    ) -> None:
        """Initialize the Matter climate entity."""
        super().__init__(matter_client, endpoint, entity_info)

        # set hvac_modes based on feature map
        self._attr_hvac_modes: list[HVACMode] = [HVACMode.OFF]
        feature_map = int(
            self.get_matter_attribute_value(clusters.Thermostat.Attributes.FeatureMap)
        )
        if feature_map & ThermostatFeature.kHeating:
            self._attr_hvac_modes.append(HVACMode.HEAT)
        if feature_map & ThermostatFeature.kCooling:
            self._attr_hvac_modes.append(HVACMode.COOL)
        if feature_map & ThermostatFeature.kAutoMode:
            self._attr_hvac_modes.append(HVACMode.HEAT_COOL)
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
            | ClimateEntityFeature.TURN_OFF
        )
        if any(mode for mode in self.hvac_modes if mode != HVACMode.OFF):
            self._attr_supported_features |= ClimateEntityFeature.TURN_ON

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
        if target_hvac_mode is not None:
            await self.async_set_hvac_mode(target_hvac_mode)

        current_mode = target_hvac_mode or self.hvac_mode
        command = None
        if current_mode in (HVACMode.HEAT, HVACMode.COOL):
            # when current mode is either heat or cool, the temperature arg must be provided.
            temperature: float | None = kwargs.get(ATTR_TEMPERATURE)
            if temperature is None:
                raise ValueError("Temperature must be provided")
            if self.target_temperature is None:
                raise ValueError("Current target_temperature should not be None")
            command = self._create_optional_setpoint_command(
                clusters.Thermostat.Enums.SetpointAdjustMode.kCool
                if current_mode == HVACMode.COOL
                else clusters.Thermostat.Enums.SetpointAdjustMode.kHeat,
                temperature,
                self.target_temperature,
            )
        elif current_mode == HVACMode.HEAT_COOL:
            temperature_low: float | None = kwargs.get(ATTR_TARGET_TEMP_LOW)
            temperature_high: float | None = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            if temperature_low is None or temperature_high is None:
                raise ValueError(
                    "temperature_low and temperature_high must be provided"
                )
            if (
                self.target_temperature_low is None
                or self.target_temperature_high is None
            ):
                raise ValueError(
                    "current target_temperature_low and target_temperature_high should not be None"
                )
            # due to ha send both high and low temperature, we need to check which one is changed
            command = self._create_optional_setpoint_command(
                clusters.Thermostat.Enums.SetpointAdjustMode.kHeat,
                temperature_low,
                self.target_temperature_low,
            )
            if command is None:
                command = self._create_optional_setpoint_command(
                    clusters.Thermostat.Enums.SetpointAdjustMode.kCool,
                    temperature_high,
                    self.target_temperature_high,
                )
        if command:
            await self.matter_client.send_device_command(
                node_id=self._endpoint.node.node_id,
                endpoint_id=self._endpoint.endpoint_id,
                command=command,
            )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        system_mode_path = create_attribute_path_from_attribute(
            endpoint_id=self._endpoint.endpoint_id,
            attribute=clusters.Thermostat.Attributes.SystemMode,
        )
        system_mode_value = HVAC_SYSTEM_MODE_MAP.get(hvac_mode)
        if system_mode_value is None:
            raise ValueError(f"Unsupported hvac mode {hvac_mode} in Matter")
        await self.matter_client.write_attribute(
            node_id=self._endpoint.node.node_id,
            attribute_path=system_mode_path,
            value=system_mode_value,
        )
        # we need to optimistically update the attribute's value here
        # to prevent a race condition when adjusting the mode and temperature
        # in the same call
        self._endpoint.set_attribute_value(system_mode_path, system_mode_value)
        self._update_from_device()

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        self._attr_current_temperature = self._get_temperature_in_degrees(
            clusters.Thermostat.Attributes.LocalTemperature
        )
        # update hvac_mode from SystemMode
        system_mode_value = int(
            self.get_matter_attribute_value(clusters.Thermostat.Attributes.SystemMode)
        )
        match system_mode_value:
            case SystemModeEnum.kAuto:
                self._attr_hvac_mode = HVACMode.HEAT_COOL
            case SystemModeEnum.kDry:
                self._attr_hvac_mode = HVACMode.DRY
            case SystemModeEnum.kFanOnly:
                self._attr_hvac_mode = HVACMode.FAN_ONLY
            case SystemModeEnum.kCool | SystemModeEnum.kPrecooling:
                self._attr_hvac_mode = HVACMode.COOL
            case SystemModeEnum.kHeat | SystemModeEnum.kEmergencyHeat:
                self._attr_hvac_mode = HVACMode.HEAT
            case _:
                self._attr_hvac_mode = HVACMode.OFF
        # running state is an optional attribute
        # which we map to hvac_action if it exists (its value is not None)
        self._attr_hvac_action = None
        if running_state_value := self.get_matter_attribute_value(
            clusters.Thermostat.Attributes.ThermostatRunningState
        ):
            match running_state_value:
                case ThermostatRunningState.Heat | ThermostatRunningState.HeatStage2:
                    self._attr_hvac_action = HVACAction.HEATING
                case ThermostatRunningState.Cool | ThermostatRunningState.CoolStage2:
                    self._attr_hvac_action = HVACAction.COOLING
                case (
                    ThermostatRunningState.Fan
                    | ThermostatRunningState.FanStage2
                    | ThermostatRunningState.FanStage3
                ):
                    self._attr_hvac_action = HVACAction.FAN
                case _:
                    self._attr_hvac_action = HVACAction.OFF
        # update target_temperature
        if self._attr_hvac_mode == HVACMode.HEAT_COOL:
            self._attr_target_temperature = None
        elif self._attr_hvac_mode == HVACMode.COOL:
            self._attr_target_temperature = self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.OccupiedCoolingSetpoint
            )
        else:
            self._attr_target_temperature = self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.OccupiedHeatingSetpoint
            )
        # update target temperature high/low
        if self._attr_hvac_mode == HVACMode.HEAT_COOL:
            self._attr_target_temperature_high = self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.OccupiedCoolingSetpoint
            )
            self._attr_target_temperature_low = self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.OccupiedHeatingSetpoint
            )
        else:
            self._attr_target_temperature_high = None
            self._attr_target_temperature_low = None
        # update min_temp
        if self._attr_hvac_mode == HVACMode.COOL:
            attribute = clusters.Thermostat.Attributes.AbsMinCoolSetpointLimit
        else:
            attribute = clusters.Thermostat.Attributes.AbsMinHeatSetpointLimit
        if (value := self._get_temperature_in_degrees(attribute)) is not None:
            self._attr_min_temp = value
        else:
            self._attr_min_temp = DEFAULT_MIN_TEMP
        # update max_temp
        if self._attr_hvac_mode in (HVACMode.COOL, HVACMode.HEAT_COOL):
            attribute = clusters.Thermostat.Attributes.AbsMaxCoolSetpointLimit
        else:
            attribute = clusters.Thermostat.Attributes.AbsMaxHeatSetpointLimit
        if (value := self._get_temperature_in_degrees(attribute)) is not None:
            self._attr_max_temp = value
        else:
            self._attr_max_temp = DEFAULT_MAX_TEMP

    def _get_temperature_in_degrees(
        self, attribute: type[clusters.ClusterAttributeDescriptor]
    ) -> float | None:
        """Return the scaled temperature value for the given attribute."""
        if value := self.get_matter_attribute_value(attribute):
            return float(value) / TEMPERATURE_SCALING_FACTOR
        return None

    @staticmethod
    def _create_optional_setpoint_command(
        mode: clusters.Thermostat.Enums.SetpointAdjustMode | int,
        target_temp: float,
        current_target_temp: float,
    ) -> clusters.Thermostat.Commands.SetpointRaiseLower | None:
        """Create a setpoint command if the target temperature is different from the current one."""

        temp_diff = int((target_temp - current_target_temp) * 10)

        if temp_diff == 0:
            return None

        return clusters.Thermostat.Commands.SetpointRaiseLower(
            mode,
            temp_diff,
        )


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.CLIMATE,
        entity_description=ClimateEntityDescription(
            key="MatterThermostat",
            name=None,
        ),
        entity_class=MatterClimate,
        required_attributes=(clusters.Thermostat.Attributes.LocalTemperature,),
        optional_attributes=(
            clusters.Thermostat.Attributes.FeatureMap,
            clusters.Thermostat.Attributes.ControlSequenceOfOperation,
            clusters.Thermostat.Attributes.Occupancy,
            clusters.Thermostat.Attributes.OccupiedCoolingSetpoint,
            clusters.Thermostat.Attributes.OccupiedHeatingSetpoint,
            clusters.Thermostat.Attributes.SystemMode,
            clusters.Thermostat.Attributes.ThermostatRunningMode,
            clusters.Thermostat.Attributes.ThermostatRunningState,
            clusters.Thermostat.Attributes.TemperatureSetpointHold,
            clusters.Thermostat.Attributes.UnoccupiedCoolingSetpoint,
            clusters.Thermostat.Attributes.UnoccupiedHeatingSetpoint,
        ),
        device_type=(device_types.Thermostat,),
    ),
]
