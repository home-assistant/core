"""Matter Number Inputs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from chip.clusters import Objects as clusters
from chip.clusters.ClusterObjects import ClusterAttributeDescriptor, ClusterCommand
from matter_server.client.models import device_types
from matter_server.common import custom_clusters

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    Platform,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MatterEntity, MatterEntityDescription
from .helpers import get_matter
from .models import MatterDiscoverySchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter Number Input from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.NUMBER, async_add_entities)


@dataclass(frozen=True, kw_only=True)
class MatterNumberEntityDescription(NumberEntityDescription, MatterEntityDescription):
    """Describe Matter Number Input entities."""


@dataclass(frozen=True, kw_only=True)
class MatterRangeNumberEntityDescription(
    NumberEntityDescription, MatterEntityDescription
):
    """Describe Matter Number Input entities with min and max values."""

    ha_to_device: Callable[[Any], Any] = lambda x: x

    # attribute descriptors to get the min and max value
    min_attribute: type[ClusterAttributeDescriptor] | None = None
    max_attribute: type[ClusterAttributeDescriptor]

    # Functions to format the min and max values for display or conversion
    format_min_value: Callable[[float], float] = lambda x: x
    format_max_value: Callable[[float], float] = lambda x: x

    # command: a custom callback to create the command to send to the device
    # the callback's argument will be the index of the selected list value
    command: Callable[[int], ClusterCommand]


class MatterNumber(MatterEntity, NumberEntity):
    """Representation of a Matter Attribute as a Number entity."""

    entity_description: MatterNumberEntityDescription

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        sendvalue = int(value)
        if value_convert := self.entity_description.ha_to_device:
            sendvalue = value_convert(value)
        await self.write_attribute(value=sendvalue)

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        value = self.get_matter_attribute_value(self._entity_info.primary_attribute)
        if value_convert := self.entity_description.device_to_ha:
            value = value_convert(value)
        self._attr_native_value = value


class MatterRangeNumber(MatterEntity, NumberEntity):
    """Representation of a Matter Attribute as a Number entity with min and max values."""

    entity_description: MatterRangeNumberEntityDescription

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        send_value = self.entity_description.ha_to_device(value)
        # custom command defined to set the new value
        await self.send_device_command(
            self.entity_description.command(send_value),
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        # get the value from the primary attribute and convert it to the HA value if needed
        value = self.get_matter_attribute_value(self._entity_info.primary_attribute)
        if value_convert := self.entity_description.device_to_ha:
            value = value_convert(value)
        self._attr_native_value = value

        # min case 1: get min from the attribute and convert it
        if self.entity_description.min_attribute:
            min_value = self.get_matter_attribute_value(
                self.entity_description.min_attribute
            )
            min_convert = self.entity_description.format_min_value
            self._attr_native_min_value = min_convert(min_value)
        # min case 2: get the min from entity_description
        elif self.entity_description.native_min_value is not None:
            self._attr_native_min_value = self.entity_description.native_min_value

        # get max from the attribute and convert it
        max_value = self.get_matter_attribute_value(
            self.entity_description.max_attribute
        )
        max_convert = self.entity_description.format_max_value
        self._attr_native_max_value = max_convert(max_value)


class MatterLevelControlNumber(MatterEntity, NumberEntity):
    """Representation of a Matter Attribute as a Number entity."""

    entity_description: MatterNumberEntityDescription

    async def async_set_native_value(self, value: float) -> None:
        """Set level value."""
        send_value = int(value)
        if value_convert := self.entity_description.ha_to_device:
            send_value = value_convert(value)
        await self.send_device_command(
            clusters.LevelControl.Commands.MoveToLevel(
                level=send_value,
            )
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        value = self.get_matter_attribute_value(self._entity_info.primary_attribute)
        if value_convert := self.entity_description.device_to_ha:
            value = value_convert(value)
        self._attr_native_value = value


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="on_level",
            entity_category=EntityCategory.CONFIG,
            translation_key="on_level",
            native_max_value=255,
            native_min_value=0,
            mode=NumberMode.BOX,
            # use 255 to indicate that the value should revert to the default
            device_to_ha=lambda x: 255 if x is None else x,
            ha_to_device=lambda x: None if x == 255 else int(x),
            native_step=1,
            native_unit_of_measurement=None,
        ),
        entity_class=MatterNumber,
        required_attributes=(clusters.LevelControl.Attributes.OnLevel,),
        not_device_type=(device_types.Speaker,),
        # allow None value to account for 'default' value
        allow_none_value=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="on_transition_time",
            entity_category=EntityCategory.CONFIG,
            translation_key="on_transition_time",
            native_max_value=65534,
            native_min_value=0,
            device_to_ha=lambda x: None if x is None else x / 10,
            ha_to_device=lambda x: round(x * 10),
            native_step=0.1,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(clusters.LevelControl.Attributes.OnTransitionTime,),
        # allow None value to account for 'default' value
        allow_none_value=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="off_transition_time",
            entity_category=EntityCategory.CONFIG,
            translation_key="off_transition_time",
            native_max_value=65534,
            native_min_value=0,
            device_to_ha=lambda x: None if x is None else x / 10,
            ha_to_device=lambda x: round(x * 10),
            native_step=0.1,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(clusters.LevelControl.Attributes.OffTransitionTime,),
        # allow None value to account for 'default' value
        allow_none_value=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="on_off_transition_time",
            entity_category=EntityCategory.CONFIG,
            translation_key="on_off_transition_time",
            native_max_value=65534,
            native_min_value=0,
            device_to_ha=lambda x: None if x is None else x / 10,
            ha_to_device=lambda x: round(x * 10),
            native_step=0.1,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(clusters.LevelControl.Attributes.OnOffTransitionTime,),
        # allow None value to account for 'default' value
        allow_none_value=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="EveWeatherAltitude",
            device_class=NumberDeviceClass.DISTANCE,
            entity_category=EntityCategory.CONFIG,
            translation_key="altitude",
            native_max_value=9000,
            native_min_value=0,
            native_unit_of_measurement=UnitOfLength.METERS,
            native_step=1,
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(custom_clusters.EveCluster.Attributes.Altitude,),
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="EveTemperatureOffset",
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
            translation_key="temperature_offset",
            native_max_value=50,
            native_min_value=-50,
            native_step=0.5,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_to_ha=lambda x: None if x is None else x / 10,
            ha_to_device=lambda x: round(x * 10),
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(
            clusters.Thermostat.Attributes.LocalTemperatureCalibration,
        ),
        vendor_id=(4874,),
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="pump_setpoint",
            native_unit_of_measurement=PERCENTAGE,
            translation_key="pump_setpoint",
            native_max_value=100,
            native_min_value=0.5,
            native_step=0.5,
            device_to_ha=(
                lambda x: None
                if x is None
                else min(x, 200) / 2  # Matter range (1-200, capped at 200)
            ),
            ha_to_device=lambda x: round(x * 2),  # HA range 0.5–100.0%
            mode=NumberMode.SLIDER,
        ),
        entity_class=MatterLevelControlNumber,
        required_attributes=(clusters.LevelControl.Attributes.CurrentLevel,),
        device_type=(device_types.Pump,),
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="PIROccupiedToUnoccupiedDelay",
            entity_category=EntityCategory.CONFIG,
            translation_key="hold_time",  # pir_occupied_to_unoccupied_delay for old revisions
            native_max_value=65534,
            native_min_value=0,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(
            clusters.OccupancySensing.Attributes.PIROccupiedToUnoccupiedDelay,
        ),
        absent_attributes=(clusters.OccupancySensing.Attributes.HoldTime,),
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="OccupancySensingHoldTime",
            entity_category=EntityCategory.CONFIG,
            translation_key="hold_time",
            native_max_value=65534,
            native_min_value=1,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(clusters.OccupancySensing.Attributes.HoldTime,),
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="ValveConfigurationAndControlDefaultOpenDuration",
            entity_category=EntityCategory.CONFIG,
            translation_key="valve_configuration_and_control_default_open_duration",
            native_max_value=65534,
            native_min_value=1,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(
            clusters.ValveConfigurationAndControl.Attributes.DefaultOpenDuration,
        ),
        allow_multi=True,
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterRangeNumberEntityDescription(
            key="MicrowaveOvenControlCookTime",
            translation_key="cook_time",
            device_class=NumberDeviceClass.DURATION,
            command=lambda value: clusters.MicrowaveOvenControl.Commands.SetCookingParameters(
                cookTime=int(value)
            ),
            native_min_value=1,  # 1 second minimum cook time
            native_step=1,  # 1 second
            native_unit_of_measurement=UnitOfTime.SECONDS,
            max_attribute=clusters.MicrowaveOvenControl.Attributes.MaxCookTime,
            mode=NumberMode.SLIDER,
        ),
        entity_class=MatterRangeNumber,
        required_attributes=(
            clusters.MicrowaveOvenControl.Attributes.CookTime,
            clusters.MicrowaveOvenControl.Attributes.MaxCookTime,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="AutoRelockTimer",
            entity_category=EntityCategory.CONFIG,
            translation_key="auto_relock_timer",
            native_max_value=65534,
            native_min_value=0,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(clusters.DoorLock.Attributes.AutoRelockTime,),
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterRangeNumberEntityDescription(
            key="TemperatureControlTemperatureSetpoint",
            name=None,
            translation_key="temperature_setpoint",
            command=lambda value: clusters.TemperatureControl.Commands.SetTemperature(
                targetTemperature=value
            ),
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_to_ha=lambda x: None if x is None else x / 100,
            ha_to_device=lambda x: round(x * 100),
            format_min_value=lambda x: x / 100,
            format_max_value=lambda x: x / 100,
            min_attribute=clusters.TemperatureControl.Attributes.MinTemperature,
            max_attribute=clusters.TemperatureControl.Attributes.MaxTemperature,
            mode=NumberMode.SLIDER,
        ),
        entity_class=MatterRangeNumber,
        required_attributes=(
            clusters.TemperatureControl.Attributes.TemperatureSetpoint,
            clusters.TemperatureControl.Attributes.MinTemperature,
            clusters.TemperatureControl.Attributes.MaxTemperature,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="InovelliLEDIndicatorIntensityOff",
            entity_category=EntityCategory.CONFIG,
            translation_key="led_indicator_intensity_off",
            native_max_value=75,
            native_min_value=0,
            native_step=1,
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(
            custom_clusters.InovelliCluster.Attributes.LEDIndicatorIntensityOff,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="InovelliLEDIndicatorIntensityOn",
            entity_category=EntityCategory.CONFIG,
            translation_key="led_indicator_intensity_on",
            native_max_value=75,
            native_min_value=0,
            native_step=1,
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(
            custom_clusters.InovelliCluster.Attributes.LEDIndicatorIntensityOn,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="DoorLockWrongCodeEntryLimit",
            entity_category=EntityCategory.CONFIG,
            translation_key="wrong_code_entry_limit",
            native_max_value=255,
            native_min_value=1,
            native_step=1,
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(clusters.DoorLock.Attributes.WrongCodeEntryLimit,),
    ),
    MatterDiscoverySchema(
        platform=Platform.NUMBER,
        entity_description=MatterNumberEntityDescription(
            key="DoorLockUserCodeTemporaryDisableTime",
            entity_category=EntityCategory.CONFIG,
            translation_key="user_code_temporary_disable_time",
            native_max_value=255,
            native_min_value=1,
            native_step=1,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            mode=NumberMode.BOX,
        ),
        entity_class=MatterNumber,
        required_attributes=(
            clusters.DoorLock.Attributes.UserCodeTemporaryDisableTime,
        ),
    ),
]
