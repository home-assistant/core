"""Matter climate platform."""
from __future__ import annotations

from typing import Any

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
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

    features: int | None = None

    _attr_temperature_unit: str = UnitOfTemperature.CELSIUS
    _attr_supported_features: ClimateEntityFeature = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        value = int(
            self.get_matter_attribute_value(clusters.Thermostat.Attributes.SystemMode)
        )
        SystemMode = clusters.Thermostat.Enums.ThermostatSystemMode

        match value:
            case SystemMode.kAuto:
                return HVACMode.HEAT_COOL
            case SystemMode.kDry:
                return HVACMode.DRY
            case SystemMode.kFanOnly:
                return HVACMode.FAN_ONLY
            case SystemMode.kCool | SystemMode.kPrecooling:
                return HVACMode.COOL
            case SystemMode.kHeat | SystemMode.kEmergencyHeat:
                return HVACMode.HEAT
            case _:
                return HVACMode.OFF

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of (currently) available hvac operation modes."""
        value = int(
            self.get_matter_attribute_value(
                clusters.Thermostat.Attributes.ControlSequenceOfOperation
            )
        )
        if value in (
            clusters.Thermostat.Enums.ThermostatControlSequence.kCoolingAndHeating,
            clusters.Thermostat.Enums.ThermostatControlSequence.kCoolingAndHeatingWithReheat,
        ):
            return [HVACMode.HEAT, HVACMode.COOL]
        if value in (
            clusters.Thermostat.Enums.ThermostatControlSequence.kCoolingOnly,
            clusters.Thermostat.Enums.ThermostatControlSequence.kCoolingWithReheat,
        ):
            return [HVACMode.COOL]
        if value in (
            clusters.Thermostat.Enums.ThermostatControlSequence.kHeatingOnly,
            clusters.Thermostat.Enums.ThermostatControlSequence.kHeatingWithReheat,
        ):
            return [HVACMode.HEAT]
        return [HVACMode.OFF]

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation (if supported)."""
        if running_state := self.get_matter_attribute_value(
            clusters.Thermostat.Attributes.ThermostatRunningState
        ):
            match running_state:
                case 1 | 8:
                    return HVACAction.HEATING
                case 2 | 16:
                    return HVACAction.COOLING
                case 4 | 32 | 64:
                    return HVACAction.FAN
                case _:
                    return HVACAction.OFF
        return None

    @property
    def min_temp(self) -> float | None:
        """Return the minimum temperature."""
        match self.hvac_mode:
            case HVACMode.COOL:
                return self._get_temperature_in_degrees(
                    clusters.Thermostat.Attributes.AbsMinCoolSetpointLimit
                )
            case HVACMode.HEAT:
                return self._get_temperature_in_degrees(
                    clusters.Thermostat.Attributes.AbsMinHeatSetpointLimit
                )
            case HVACMode.HEAT_COOL:
                return self._get_temperature_in_degrees(
                    clusters.Thermostat.Attributes.AbsMinHeatSetpointLimit
                )
            case _:
                return None

    @property
    def max_temp(self) -> float | None:
        """Return the maximum temperature."""
        match self.hvac_mode:
            case HVACMode.COOL:
                return self._get_temperature_in_degrees(
                    clusters.Thermostat.Attributes.AbsMaxCoolSetpointLimit
                )
            case HVACMode.HEAT:
                return self._get_temperature_in_degrees(
                    clusters.Thermostat.Attributes.AbsMaxHeatSetpointLimit
                )
            case HVACMode.HEAT_COOL:
                return self._get_temperature_in_degrees(
                    clusters.Thermostat.Attributes.AbsMaxCoolSetpointLimit
                )
            case _:
                return None

    def _get_temperature_in_degrees(
        self, attribute: type[clusters.ClusterAttributeDescriptor]
    ) -> float | None:
        """Return the scaled temperature value for the given attribute."""
        if value := self.get_matter_attribute_value(attribute):
            return float(value) / TEMPERATURE_SCALING_FACTOR
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._get_temperature_in_degrees(
            clusters.Thermostat.Attributes.LocalTemperature
        )

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        match self.hvac_mode:
            case HVACMode.COOL:
                return self._get_temperature_in_degrees(
                    clusters.Thermostat.Attributes.OccupiedCoolingSetpoint
                )
            case HVACMode.HEAT:
                return self._get_temperature_in_degrees(
                    clusters.Thermostat.Attributes.OccupiedHeatingSetpoint
                )
            case _:
                return None

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.OccupiedCoolingSetpoint
            )

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.OccupiedHeatingSetpoint
            )

    @staticmethod
    def create_optional_setpoint_command(
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

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        match self.hvac_mode:
            case HVACMode.HEAT:
                command = self.create_optional_setpoint_command(
                    clusters.Thermostat.Enums.SetpointAdjustMode.kHeat,
                    kwargs.get(ATTR_TEMPERATURE),
                    self.target_temperature,
                )
            case HVACMode.COOL:
                command = self.create_optional_setpoint_command(
                    clusters.Thermostat.Enums.SetpointAdjustMode.kCool,
                    kwargs.get(ATTR_TEMPERATURE),
                    self.target_temperature,
                )
            case HVACMode.HEAT_COOL:
                # due to ha send both high and low temperature, we need to check which one is changed
                command = self.create_optional_setpoint_command(
                    clusters.Thermostat.Enums.SetpointAdjustMode.kHeat,
                    kwargs.get(ATTR_TARGET_TEMP_LOW),
                    self.target_temperature_low,
                )

                if command is None:
                    command = self.create_optional_setpoint_command(
                        clusters.Thermostat.Enums.SetpointAdjustMode.kCool,
                        kwargs.get(ATTR_TARGET_TEMP_HIGH),
                        self.target_temperature_high,
                    )
            case _:
                # Uncertain if there are any modes in HA other than heat and cool that can set the target temperature.
                return

        if command:
            await self.matter_client.send_device_command(
                node_id=self._endpoint.node.node_id,
                endpoint_id=self._endpoint.endpoint_id,
                command=command,
            )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        # work out supported features and modes
        self.features = self.get_matter_attribute_value(
            clusters.Thermostat.Attributes.FeatureMap
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
