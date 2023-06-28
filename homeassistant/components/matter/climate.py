"""Matter climate platform."""
from __future__ import annotations

from typing import Any

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types

from homeassistant.components.climate import (
    ClimateEntityDescription,
    ClimateEntity,
    ClimateEntityFeature,
)
from homeassistant.components.climate.const import HVACAction, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema


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
    )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        value = int(
            self.get_matter_attribute_value(clusters.Thermostat.Attributes.SystemMode)
        )
        if value == clusters.Thermostat.Enums.ThermostatSystemMode.kAuto:
            return HVACMode.AUTO
        if value == clusters.Thermostat.Enums.ThermostatSystemMode.kDry:
            return HVACMode.DRY
        if value == clusters.Thermostat.Enums.ThermostatSystemMode.kFanOnly:
            return HVACMode.FAN_ONLY
        if value in (
            clusters.Thermostat.Enums.ThermostatSystemMode.kCool,
            clusters.Thermostat.Enums.ThermostatSystemMode.kPrecooling,
        ):
            return HVACMode.COOL
        if value in (
            clusters.Thermostat.Enums.ThermostatSystemMode.kHeat,
            clusters.Thermostat.Enums.ThermostatSystemMode.kEmergencyHeat,
        ):
            return HVACMode.HEAT
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
            if running_state == 0:
                return HVACAction.HEATING
            if running_state == 1:
                return HVACAction.COOLING
            if running_state == 2:
                return HVACAction.FAN
        if running_mode := self.get_matter_attribute_value(
            clusters.Thermostat.Attributes.ThermostatRunningMode
        ):
            if running_mode == clusters.Thermostat.Enums.ThermostatRunningMode.kCool:
                return HVACAction.COOLING
            if running_mode == clusters.Thermostat.Enums.ThermostatRunningMode.kHeat:
                return HVACAction.HEATING
            if running_mode == clusters.Thermostat.Enums.ThermostatRunningMode.kOff:
                return HVACAction.OFF
        return None

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity level (if supported)."""

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if value := self.get_matter_attribute_value(
            clusters.Thermostat.Attributes.LocalTemperature
        ):
            assert isinstance(value, float)
            return value / 100
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVACMode.COOL:
            if value := self.get_matter_attribute_value(
                clusters.Thermostat.Attributes.OccupiedCoolingSetpoint
            ):
                assert isinstance(value, float)
                return value / 100
        if value := self.get_matter_attribute_value(
            clusters.Thermostat.Attributes.OccupiedHeatingSetpoint
        ):
            assert isinstance(value, float)
            return value / 100
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_temp: float | None = kwargs.get(ATTR_TEMPERATURE)

        if target_temp is None or self.target_temperature is None:
            return

        temp_diff = int((target_temp - self.target_temperature) * 10)

        match self.hvac_mode:
            case HVACMode.HEAT:
                command = clusters.Thermostat.Commands.SetpointRaiseLower(
                    clusters.Thermostat.Enums.SetpointAdjustMode.kHeatSetpoint,
                    temp_diff,
                )
            case HVACMode.COOL:
                command = clusters.Thermostat.Commands.SetpointRaiseLower(
                    clusters.Thermostat.Enums.SetpointAdjustMode.kCoolSetpoint,
                    temp_diff,
                )
            case HVACMode.AUTO:
                # not sure how to handle this when system is in auto mode
                command = clusters.Thermostat.Commands.SetpointRaiseLower(
                    clusters.Thermostat.Enums.SetpointAdjustMode.kHeatAndCoolSetpoints,
                    temp_diff,
                )
            case _:
                return

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

        if value := self.get_matter_attribute_value(
            clusters.Thermostat.Attributes.LocalTemperature
        ):
            self._attr_current_temperature = value / 100
            print("current temp", self._attr_current_temperature)

        match self.hvac_mode:
            case HVACMode.COOL:
                target_temp = self.get_matter_attribute_value(
                    clusters.Thermostat.Attributes.OccupiedCoolingSetpoint
                )
                self._attr_target_temperature = target_temp
                print("target temp", self._attr_target_temperature)
            case HVACMode.HEAT:
                target_temp = self.get_matter_attribute_value(
                    clusters.Thermostat.Attributes.OccupiedHeatingSetpoint
                )
                self._attr_target_temperature = target_temp
                print("target temp", self._attr_target_temperature)
            case HVACMode.AUTO:
                # When the system mode is set to "auto," there is no target temperature; instead, there is a target temperature low and high.
                pass
            case _:
                pass


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.CLIMATE,
        entity_description=ClimateEntityDescription(key="MatterThermostat"),
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
