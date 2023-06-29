"""Matter climate platform."""
from __future__ import annotations

from typing import Any

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types
from matter_server.common.helpers.util import create_attribute_path_from_attribute

from homeassistant.components.climate import (
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

TEMPERATURE_SCALING_FACTOR = 100
SystemModeEnum = clusters.Thermostat.Enums.ThermostatSystemMode
ControlSequenceEnum = clusters.Thermostat.Enums.ThermostatControlSequence


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
    _attr_supported_features: ClimateEntityFeature = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )
    _attr_hvac_mode: HVACMode = HVACMode.OFF
    _attr_hvac_modes: list[HVACMode] = [HVACMode.OFF]

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        value: float | None = None
        if self._attr_hvac_mode == HVACMode.COOL:
            value = self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.AbsMinCoolSetpointLimit
            )
        elif self._attr_hvac_mode == HVACMode.HEAT:
            value = self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.AbsMinHeatSetpointLimit
            )
        elif self._attr_hvac_mode == HVACMode.HEAT_COOL:
            value = self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.AbsMinHeatSetpointLimit
            )
        if value is not None:
            return value
        return DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        value: float | None = None
        if self._attr_hvac_mode == HVACMode.COOL:
            value = self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.AbsMaxCoolSetpointLimit
            )
        elif self._attr_hvac_mode == HVACMode.HEAT:
            value = self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.AbsMaxHeatSetpointLimit
            )
        elif self._attr_hvac_mode == HVACMode.HEAT_COOL:
            value = self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.AbsMaxCoolSetpointLimit
            )
        if value is not None:
            return value
        return DEFAULT_MAX_TEMP

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self._attr_hvac_mode == HVACMode.COOL:
            return self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.OccupiedCoolingSetpoint
            )
        return self._get_temperature_in_degrees(
            clusters.Thermostat.Attributes.OccupiedHeatingSetpoint
        )

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        return self._get_temperature_in_degrees(
            clusters.Thermostat.Attributes.OccupiedCoolingSetpoint
        )

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        return self._get_temperature_in_degrees(
            clusters.Thermostat.Attributes.OccupiedHeatingSetpoint
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        current_mode = self.hvac_mode
        if current_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL):
            # when current mode is either heat or cool, the temperature arg must be provided.
            temperature = kwargs.get(ATTR_TEMPERATURE)
            if temperature is None:
                raise ValueError("Temperature must be provided")
            command = self._create_optional_setpoint_command(
                clusters.Thermostat.Enums.SetpointAdjustMode.kCool
                if current_mode == HVACMode.COOL
                else clusters.Thermostat.Enums.SetpointAdjustMode.kHeat,
                temperature,
                self.target_temperature,
            )
        elif current_mode == HVACMode.HEAT_COOL:
            temperature_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
            temperature_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            if temperature_low is None and temperature_high is None:
                raise ValueError(
                    "temperature_low and/or temperature_high must be provided"
                )
            # due to ha send both high and low temperature, we need to check which one is changed
            command = self._create_optional_setpoint_command(
                clusters.Thermostat.Enums.SetpointAdjustMode.kHeat,
                kwargs.get(ATTR_TARGET_TEMP_LOW),
                self.target_temperature_low,
            )
            if command is None:
                command = self._create_optional_setpoint_command(
                    clusters.Thermostat.Enums.SetpointAdjustMode.kCool,
                    kwargs.get(ATTR_TARGET_TEMP_HIGH),
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
        hvac_system_mode_map = {
            HVACMode.HEAT: 4,
            HVACMode.COOL: 3,
            HVACMode.HEAT_COOL: 1,
        }
        system_mode_path = create_attribute_path_from_attribute(
            endpoint_id=self._endpoint.endpoint_id,
            attribute=clusters.Thermostat.Attributes.SystemMode,
        )
        system_mode_value = hvac_system_mode_map.get(hvac_mode)
        if system_mode_value is None:
            return
        await self.matter_client.write_attribute(
            node_id=self._endpoint.node.node_id,
            attribute_path=system_mode_path,
            value=system_mode_value,
        )

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
                case 1 | 8:
                    self._attr_hvac_action = HVACAction.HEATING
                case 2 | 16:
                    self._attr_hvac_action = HVACAction.COOLING
                case 4 | 32 | 64:
                    self._attr_hvac_action = HVACAction.FAN
                case _:
                    self._attr_hvac_action = HVACAction.OFF
        # update hvac_modes based on ControlSequenceOfOperation
        control_sequence_value = int(
            self.get_matter_attribute_value(
                clusters.Thermostat.Attributes.ControlSequenceOfOperation
            )
        )
        match control_sequence_value:
            case ControlSequenceEnum.kCoolingAndHeating | ControlSequenceEnum.kCoolingAndHeatingWithReheat:
                self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL]
            case ControlSequenceEnum.kCoolingOnly | ControlSequenceEnum.kCoolingWithReheat:
                self._attr_hvac_modes = [HVACMode.COOL]
            case ControlSequenceEnum.kHeatingOnly | ControlSequenceEnum.kHeatingWithReheat:
                self._attr_hvac_modes = [HVACMode.HEAT]
            case _:
                self._attr_hvac_modes = [HVACMode.OFF]

    def _get_temperature_in_degrees(
        self, attribute: type[clusters.ClusterAttributeDescriptor]
    ) -> float | None:
        """Return the scaled temperature value for the given attribute."""
        if value := self.get_matter_attribute_value(attribute):
            return float(value) / TEMPERATURE_SCALING_FACTOR
        return None

    @staticmethod
    def _create_optional_setpoint_command(
        mode: clusters.Thermostat.Enums.SetpointAdjustMode,
        target_temp: float | None,
        current_target_temp: float | None,
    ) -> clusters.Thermostat.Commands.SetpointRaiseLower | None:
        """Create a setpoint command if the target temperature is different from the current one."""
        if target_temp is None or current_target_temp is None:
            return None

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
