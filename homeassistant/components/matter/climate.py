"""Matter climate platform."""

from __future__ import annotations

from enum import IntEnum
from typing import Any

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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MatterEntity
from .helpers import get_matter
from .models import MatterDiscoverySchema

TEMPERATURE_SCALING_FACTOR = 100
HVAC_SYSTEM_MODE_MAP = {
    HVACMode.OFF: 0,
    HVACMode.HEAT_COOL: 1,
    HVACMode.COOL: 3,
    HVACMode.HEAT: 4,
    HVACMode.DRY: 8,
    HVACMode.FAN_ONLY: 7,
}

SINGLE_SETPOINT_DEVICES: set[tuple[int, int]] = {
    # Some devices only have a single setpoint while the matter spec
    # assumes that you need separate setpoints for heating and cooling.
    # We were told this is just some legacy inheritance from zigbee specs.
    # In the list below specify tuples of (vendorid, productid) of devices for
    # which we just need a single setpoint to control both heating and cooling.
    (0x1209, 0x8000),
    (0x1209, 0x8001),
    (0x1209, 0x8002),
    (0x1209, 0x8003),
    (0x1209, 0x8004),
    (0x1209, 0x8005),
    (0x1209, 0x8006),
    (0x1209, 0x8007),
    (0x1209, 0x8008),
    (0x1209, 0x8009),
    (0x1209, 0x800A),
    (0x1209, 0x800B),
    (0x1209, 0x800C),
    (0x1209, 0x800D),
    (0x1209, 0x800E),
    (0x1209, 0x8010),
    (0x1209, 0x8011),
    (0x1209, 0x8012),
    (0x1209, 0x8013),
    (0x1209, 0x8014),
    (0x1209, 0x8020),
    (0x1209, 0x8021),
    (0x1209, 0x8022),
    (0x1209, 0x8023),
    (0x1209, 0x8024),
    (0x1209, 0x8025),
    (0x1209, 0x8026),
    (0x1209, 0x8027),
    (0x1209, 0x8028),
    (0x1209, 0x8029),
}

SUPPORT_DRY_MODE_DEVICES: set[tuple[int, int]] = {
    # The Matter spec is missing a feature flag if the device supports a dry mode.
    # In the list below specify tuples of (vendorid, productid) of devices that
    # support dry mode.
    (0x0001, 0x0108),
    (0x0001, 0x010A),
    (0x1209, 0x8000),
    (0x1209, 0x8001),
    (0x1209, 0x8002),
    (0x1209, 0x8003),
    (0x1209, 0x8004),
    (0x1209, 0x8005),
    (0x1209, 0x8006),
    (0x1209, 0x8007),
    (0x1209, 0x8008),
    (0x1209, 0x8009),
    (0x1209, 0x800A),
    (0x1209, 0x800B),
    (0x1209, 0x800C),
    (0x1209, 0x800D),
    (0x1209, 0x800E),
    (0x1209, 0x8010),
    (0x1209, 0x8011),
    (0x1209, 0x8012),
    (0x1209, 0x8013),
    (0x1209, 0x8014),
    (0x1209, 0x8020),
    (0x1209, 0x8021),
    (0x1209, 0x8022),
    (0x1209, 0x8023),
    (0x1209, 0x8024),
    (0x1209, 0x8025),
    (0x1209, 0x8026),
    (0x1209, 0x8027),
    (0x1209, 0x8028),
    (0x1209, 0x8029),
}

SUPPORT_FAN_MODE_DEVICES: set[tuple[int, int]] = {
    # The Matter spec is missing a feature flag if the device supports a fan-only mode.
    # In the list below specify tuples of (vendorid, productid) of devices that
    # support fan-only mode.
    (0x0001, 0x0108),
    (0x0001, 0x010A),
    (0x1209, 0x8000),
    (0x1209, 0x8001),
    (0x1209, 0x8002),
    (0x1209, 0x8003),
    (0x1209, 0x8004),
    (0x1209, 0x8005),
    (0x1209, 0x8006),
    (0x1209, 0x8007),
    (0x1209, 0x8008),
    (0x1209, 0x8009),
    (0x1209, 0x800A),
    (0x1209, 0x800B),
    (0x1209, 0x800C),
    (0x1209, 0x800D),
    (0x1209, 0x800E),
    (0x1209, 0x8010),
    (0x1209, 0x8011),
    (0x1209, 0x8012),
    (0x1209, 0x8013),
    (0x1209, 0x8014),
    (0x1209, 0x8020),
    (0x1209, 0x8021),
    (0x1209, 0x8022),
    (0x1209, 0x8023),
    (0x1209, 0x8024),
    (0x1209, 0x8025),
    (0x1209, 0x8026),
    (0x1209, 0x8027),
    (0x1209, 0x8028),
    (0x1209, 0x8029),
}

SystemModeEnum = clusters.Thermostat.Enums.SystemModeEnum
ControlSequenceEnum = clusters.Thermostat.Enums.ControlSequenceOfOperationEnum
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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter climate platform from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.CLIMATE, async_add_entities)


class MatterClimate(MatterEntity, ClimateEntity):
    """Representation of a Matter climate entity."""

    _attr_temperature_unit: str = UnitOfTemperature.CELSIUS
    _attr_hvac_mode: HVACMode = HVACMode.OFF
    _feature_map: int | None = None

    _platform_translation_key = "thermostat"

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        target_hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
        target_temperature: float | None = kwargs.get(ATTR_TEMPERATURE)
        target_temperature_low: float | None = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temperature_high: float | None = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        if target_hvac_mode is not None:
            await self.async_set_hvac_mode(target_hvac_mode)
        current_mode = target_hvac_mode or self.hvac_mode

        if target_temperature is not None:
            # single setpoint control
            if self.target_temperature != target_temperature:
                if current_mode == HVACMode.COOL:
                    matter_attribute = (
                        clusters.Thermostat.Attributes.OccupiedCoolingSetpoint
                    )
                else:
                    matter_attribute = (
                        clusters.Thermostat.Attributes.OccupiedHeatingSetpoint
                    )
                await self.write_attribute(
                    value=int(target_temperature * TEMPERATURE_SCALING_FACTOR),
                    matter_attribute=matter_attribute,
                )
            return

        if target_temperature_low is not None:
            # multi setpoint control - low setpoint (heat)
            if self.target_temperature_low != target_temperature_low:
                await self.write_attribute(
                    value=int(target_temperature_low * TEMPERATURE_SCALING_FACTOR),
                    matter_attribute=clusters.Thermostat.Attributes.OccupiedHeatingSetpoint,
                )

        if target_temperature_high is not None:
            # multi setpoint control - high setpoint (cool)
            if self.target_temperature_high != target_temperature_high:
                await self.write_attribute(
                    value=int(target_temperature_high * TEMPERATURE_SCALING_FACTOR),
                    matter_attribute=clusters.Thermostat.Attributes.OccupiedCoolingSetpoint,
                )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""

        system_mode_value = HVAC_SYSTEM_MODE_MAP.get(hvac_mode)
        if system_mode_value is None:
            raise ValueError(f"Unsupported hvac mode {hvac_mode} in Matter")
        await self.write_attribute(
            value=system_mode_value,
            matter_attribute=clusters.Thermostat.Attributes.SystemMode,
        )
        # we need to optimistically update the attribute's value here
        # to prevent a race condition when adjusting the mode and temperature
        # in the same call
        system_mode_path = create_attribute_path_from_attribute(
            endpoint_id=self._endpoint.endpoint_id,
            attribute=clusters.Thermostat.Attributes.SystemMode,
        )
        self._endpoint.set_attribute_value(system_mode_path, system_mode_value)
        self._update_from_device()

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        self._calculate_features()
        self._attr_current_temperature = self._get_temperature_in_degrees(
            clusters.Thermostat.Attributes.LocalTemperature
        )
        if self.get_matter_attribute_value(clusters.OnOff.Attributes.OnOff) is False:
            # special case: the appliance has a dedicated Power switch on the OnOff cluster
            # if the mains power is off - treat it as if the HVAC mode is off
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = None
        else:
            # update hvac_mode from SystemMode
            system_mode_value = int(
                self.get_matter_attribute_value(
                    clusters.Thermostat.Attributes.SystemMode
                )
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
                case SystemModeEnum.kFanOnly:
                    self._attr_hvac_mode = HVACMode.FAN_ONLY
                case SystemModeEnum.kDry:
                    self._attr_hvac_mode = HVACMode.DRY
                case _:
                    self._attr_hvac_mode = HVACMode.OFF
            # running state is an optional attribute
            # which we map to hvac_action if it exists (its value is not None)
            self._attr_hvac_action = None
            if running_state_value := self.get_matter_attribute_value(
                clusters.Thermostat.Attributes.ThermostatRunningState
            ):
                match running_state_value:
                    case (
                        ThermostatRunningState.Heat | ThermostatRunningState.HeatStage2
                    ):
                        self._attr_hvac_action = HVACAction.HEATING
                    case (
                        ThermostatRunningState.Cool | ThermostatRunningState.CoolStage2
                    ):
                        self._attr_hvac_action = HVACAction.COOLING
                    case (
                        ThermostatRunningState.Fan
                        | ThermostatRunningState.FanStage2
                        | ThermostatRunningState.FanStage3
                    ):
                        self._attr_hvac_action = HVACAction.FAN
                    case _:
                        self._attr_hvac_action = HVACAction.OFF

        # update target temperature high/low
        supports_range = (
            self._attr_supported_features
            & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        )
        if supports_range and self._attr_hvac_mode == HVACMode.HEAT_COOL:
            self._attr_target_temperature = None
            self._attr_target_temperature_high = self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.OccupiedCoolingSetpoint
            )
            self._attr_target_temperature_low = self._get_temperature_in_degrees(
                clusters.Thermostat.Attributes.OccupiedHeatingSetpoint
            )
        else:
            self._attr_target_temperature_high = None
            self._attr_target_temperature_low = None
            # update target_temperature
            if self._attr_hvac_mode == HVACMode.COOL:
                self._attr_target_temperature = self._get_temperature_in_degrees(
                    clusters.Thermostat.Attributes.OccupiedCoolingSetpoint
                )
            else:
                self._attr_target_temperature = self._get_temperature_in_degrees(
                    clusters.Thermostat.Attributes.OccupiedHeatingSetpoint
                )

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

    @callback
    def _calculate_features(
        self,
    ) -> None:
        """Calculate features for HA Thermostat platform from Matter FeatureMap."""
        feature_map = int(
            self.get_matter_attribute_value(clusters.Thermostat.Attributes.FeatureMap)
        )
        # NOTE: the featuremap can dynamically change, so we need to update the
        # supported features if the featuremap changes.
        # work out supported features and presets from matter featuremap
        if self._feature_map == feature_map:
            return
        self._feature_map = feature_map
        product_id = self._endpoint.node.device_info.productID
        vendor_id = self._endpoint.node.device_info.vendorID
        self._attr_hvac_modes: list[HVACMode] = [HVACMode.OFF]
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_OFF
        )
        if feature_map & ThermostatFeature.kHeating:
            self._attr_hvac_modes.append(HVACMode.HEAT)
        if feature_map & ThermostatFeature.kCooling:
            self._attr_hvac_modes.append(HVACMode.COOL)
        if (vendor_id, product_id) in SUPPORT_DRY_MODE_DEVICES:
            self._attr_hvac_modes.append(HVACMode.DRY)
        if (vendor_id, product_id) in SUPPORT_FAN_MODE_DEVICES:
            self._attr_hvac_modes.append(HVACMode.FAN_ONLY)
        if feature_map & ThermostatFeature.kAutoMode:
            self._attr_hvac_modes.append(HVACMode.HEAT_COOL)
            # only enable temperature_range feature if the device actually supports that

            if (vendor_id, product_id) not in SINGLE_SETPOINT_DEVICES:
                self._attr_supported_features |= (
                    ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
                )
        if any(mode for mode in self.hvac_modes if mode != HVACMode.OFF):
            self._attr_supported_features |= ClimateEntityFeature.TURN_ON

    @callback
    def _get_temperature_in_degrees(
        self, attribute: type[clusters.ClusterAttributeDescriptor]
    ) -> float | None:
        """Return the scaled temperature value for the given attribute."""
        if value := self.get_matter_attribute_value(attribute):
            return float(value) / TEMPERATURE_SCALING_FACTOR
        return None


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
            clusters.OnOff.Attributes.OnOff,
        ),
        device_type=(device_types.Thermostat, device_types.RoomAirConditioner),
        allow_multi=True,  # also used for sensor entity
    ),
]
