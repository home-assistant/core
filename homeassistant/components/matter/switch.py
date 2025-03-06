"""Matter switches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chip.clusters import Objects as clusters
from matter_server.client.models import device_types

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
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
    """Set up Matter switches from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.SWITCH, async_add_entities)


class MatterSwitch(MatterEntity, SwitchEntity):
    """Representation of a Matter switch."""

    _platform_translation_key = "switch"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        await self.send_device_command(
            clusters.OnOff.Commands.On(),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        await self.send_device_command(
            clusters.OnOff.Commands.Off(),
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        self._attr_is_on = self.get_matter_attribute_value(
            self._entity_info.primary_attribute
        )


@dataclass(frozen=True)
class MatterNumericSwitchEntityDescription(
    SwitchEntityDescription, MatterEntityDescription
):
    """Describe Matter Numeric Switch entities."""


class MatterNumericSwitch(MatterSwitch):
    """Representation of a Matter Enum Attribute as a Switch entity."""

    entity_description: MatterNumericSwitchEntityDescription

    async def _async_set_native_value(self, value: bool) -> None:
        """Update the current value."""
        if value_convert := self.entity_description.ha_to_native_value:
            send_value = value_convert(value)
        await self.write_attribute(
            value=send_value,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        await self._async_set_native_value(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        await self._async_set_native_value(False)

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        value = self.get_matter_attribute_value(self._entity_info.primary_attribute)
        if value_convert := self.entity_description.measurement_to_ha:
            value = value_convert(value)
        self._attr_is_on = value


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.SWITCH,
        entity_description=SwitchEntityDescription(
            key="MatterPlug",
            device_class=SwitchDeviceClass.OUTLET,
            name=None,
        ),
        entity_class=MatterSwitch,
        required_attributes=(clusters.OnOff.Attributes.OnOff,),
        device_type=(device_types.OnOffPlugInUnit,),
    ),
    MatterDiscoverySchema(
        platform=Platform.SWITCH,
        entity_description=SwitchEntityDescription(
            key="MatterPowerToggle",
            device_class=SwitchDeviceClass.SWITCH,
            translation_key="power",
        ),
        entity_class=MatterSwitch,
        required_attributes=(clusters.OnOff.Attributes.OnOff,),
        device_type=(
            device_types.AirPurifier,
            device_types.BasicVideoPlayer,
            device_types.CastingVideoPlayer,
            device_types.CookSurface,
            device_types.Cooktop,
            device_types.Dishwasher,
            device_types.ExtractorHood,
            device_types.HeatingCoolingUnit,
            device_types.LaundryDryer,
            device_types.LaundryWasher,
            device_types.Oven,
            device_types.Pump,
            device_types.PumpController,
            device_types.Refrigerator,
            device_types.RoboticVacuumCleaner,
            device_types.RoomAirConditioner,
            device_types.Speaker,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SWITCH,
        entity_description=SwitchEntityDescription(
            key="MatterSwitch",
            device_class=SwitchDeviceClass.OUTLET,
            name=None,
        ),
        entity_class=MatterSwitch,
        required_attributes=(clusters.OnOff.Attributes.OnOff,),
        not_device_type=(
            device_types.ColorTemperatureLight,
            device_types.DimmableLight,
            device_types.ExtendedColorLight,
            device_types.DimmerSwitch,
            device_types.ColorDimmerSwitch,
            device_types.OnOffLight,
            device_types.AirPurifier,
            device_types.BasicVideoPlayer,
            device_types.CastingVideoPlayer,
            device_types.CookSurface,
            device_types.Cooktop,
            device_types.Dishwasher,
            device_types.ExtractorHood,
            device_types.Fan,
            device_types.HeatingCoolingUnit,
            device_types.LaundryDryer,
            device_types.LaundryWasher,
            device_types.Oven,
            device_types.Pump,
            device_types.PumpController,
            device_types.Refrigerator,
            device_types.RoboticVacuumCleaner,
            device_types.RoomAirConditioner,
            device_types.Speaker,
        ),
    ),
    MatterDiscoverySchema(
        platform=Platform.SWITCH,
        entity_description=MatterNumericSwitchEntityDescription(
            key="EveTrvChildLock",
            entity_category=EntityCategory.CONFIG,
            translation_key="child_lock",
            measurement_to_ha={
                0: False,
                1: True,
            }.get,
            ha_to_native_value={
                False: 0,
                True: 1,
            }.get,
        ),
        entity_class=MatterNumericSwitch,
        required_attributes=(
            clusters.ThermostatUserInterfaceConfiguration.Attributes.KeypadLockout,
        ),
        vendor_id=(4874,),
    ),
]
