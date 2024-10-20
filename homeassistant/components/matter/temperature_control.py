"""Matter temperature control platform."""

from __future__ import annotations

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
TCTL_SYSTEM_MODE_MAP = {
    HVACMode.TN: 0,
    HVACMode.TL: 1,
    HVACMode.STEP: 2,
}


SystemModeEnum = clusters.TemperatureControl.Enums.SystemModeEnum
ControlSequenceEnum = clusters.TemperatureControl.Enums.ControlSequenceOfOperationEnum
TemperatureControlFeature = clusters.TemperatureControl.Bitmaps.Feature


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
    _feature_map: int | None = None
    _enable_turn_on_off_backwards_compatibility = False

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
                        clusters.TemperatureControl.Attributes.OccupiedCoolingSetpoint
                    )
                else:
                    matter_attribute = (
                        clusters.TemperatureControl.Attributes.OccupiedHeatingSetpoint
                    )
                await self.matter_client.write_attribute(
                    node_id=self._endpoint.node.node_id,
                    attribute_path=create_attribute_path_from_attribute(
                        self._endpoint.endpoint_id,
                        matter_attribute,
                    ),
                    value=int(target_temperature * TEMPERATURE_SCALING_FACTOR),
                )
            return

        if target_temperature_low is not None:
            # multi setpoint control - low setpoint (heat)
            if self.target_temperature_low != target_temperature_low:
                await self.matter_client.write_attribute(
                    node_id=self._endpoint.node.node_id,
                    attribute_path=create_attribute_path_from_attribute(
                        self._endpoint.endpoint_id,
                        clusters.TemperatureControl.Attributes.OccupiedHeatingSetpoint,
                    ),
                    value=int(target_temperature_low * TEMPERATURE_SCALING_FACTOR),
                )

        if target_temperature_high is not None:
            # multi setpoint control - high setpoint (cool)
            if self.target_temperature_high != target_temperature_high:
                await self.matter_client.write_attribute(
                    node_id=self._endpoint.node.node_id,
                    attribute_path=create_attribute_path_from_attribute(
                        self._endpoint.endpoint_id,
                        clusters.TemperatureControl.Attributes.OccupiedCoolingSetpoint,
                    ),
                    value=int(target_temperature_high * TEMPERATURE_SCALING_FACTOR),
                )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        system_mode_path = create_attribute_path_from_attribute(
            endpoint_id=self._endpoint.endpoint_id,
            attribute=clusters.TemperatureControl.Attributes.SystemMode,
        )
        system_mode_value = TCTL_SYSTEM_MODE_MAP.get(hvac_mode)
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
        self._calculate_features()
        self._attr_current_temperature = self._get_temperature_in_degrees(
            clusters.TemperatureControl.Attributes.LocalTemperature
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
                    clusters.TemperatureControl.Attributes.SystemMode
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

        # update target temperature high/low
        supports_range = (
            self._attr_supported_features
            & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        )
        if supports_range and self._attr_hvac_mode == HVACMode.HEAT_COOL:
            self._attr_target_temperature = None
            self._attr_target_temperature_high = self._get_temperature_in_degrees(
                clusters.TemperatureControl.Attributes.OccupiedCoolingSetpoint
            )
            self._attr_target_temperature_low = self._get_temperature_in_degrees(
                clusters.TemperatureControl.Attributes.OccupiedHeatingSetpoint
            )
        else:
            self._attr_target_temperature_high = None
            self._attr_target_temperature_low = None
            # update target_temperature
            if self._attr_hvac_mode == HVACMode.COOL:
                self._attr_target_temperature = self._get_temperature_in_degrees(
                    clusters.TemperatureControl.Attributes.OccupiedCoolingSetpoint
                )
            else:
                self._attr_target_temperature = self._get_temperature_in_degrees(
                    clusters.TemperatureControl.Attributes.OccupiedHeatingSetpoint
                )

        # update min_temp
        if self._attr_hvac_mode == HVACMode.COOL:
            attribute = clusters.TemperatureControl.Attributes.AbsMinCoolSetpointLimit
        else:
            attribute = clusters.TemperatureControl.Attributes.AbsMinHeatSetpointLimit
        if (value := self._get_temperature_in_degrees(attribute)) is not None:
            self._attr_min_temp = value
        else:
            self._attr_min_temp = DEFAULT_MIN_TEMP
        # update max_temp
        if self._attr_hvac_mode in (HVACMode.COOL, HVACMode.HEAT_COOL):
            attribute = clusters.TemperatureControl.Attributes.AbsMaxCoolSetpointLimit
        else:
            attribute = clusters.TemperatureControl.Attributes.AbsMaxHeatSetpointLimit
        if (value := self._get_temperature_in_degrees(attribute)) is not None:
            self._attr_max_temp = value
        else:
            self._attr_max_temp = DEFAULT_MAX_TEMP

    @callback
    def _calculate_features(
        self,
    ) -> None:
        """Calculate features for HA TemperatureControl platform from Matter FeatureMap."""
        feature_map = int(
            self.get_matter_attribute_value(
                clusters.TemperatureControl.Attributes.FeatureMap
            )
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
        # TemperatureLevel feature
        if feature_map & TemperatureControlFeature.kTN:
            self._attr_hvac_modes.append(HVACMode.HEAT)
        # TemperatureLevel feature
        if feature_map & TemperatureControlFeature.kTL:
            self._attr_hvac_modes.append(HVACMode.COOL)
        # TemperatureStep feature
        if feature_map & TemperatureControlFeature.kSTEP:
            self._attr_hvac_modes.append(HVACMode.HEAT_COOL)
            # only enable temperature_range feature if the device actually supports that

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
            key="MatterTemperatureControl",
            translation_key="thermostat",
        ),
        entity_class=MatterClimate,
        required_attributes=(clusters.TemperatureControl.Attributes.FeatureMap,),
        optional_attributes=(),
        device_type=(
            device_types.CookSurface,
            device_types.Dishwasher,
            device_types.HeatingCoolingUnit,
            device_types.LaundryDryer,
            device_types.LaundryWasher,
        ),
    ),
]
