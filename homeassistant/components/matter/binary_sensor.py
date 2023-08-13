"""Matter binary sensors."""
from __future__ import annotations

from dataclasses import dataclass

from chip.clusters import Objects as clusters
from chip.clusters.Objects import uint
from chip.clusters.Types import Nullable, NullValue

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MatterEntity, MatterEntityDescription
from .helpers import get_matter
from .models import MatterDiscoverySchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter binary sensor from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.BINARY_SENSOR, async_add_entities)


@dataclass
class MatterBinarySensorEntityDescription(
    BinarySensorEntityDescription, MatterEntityDescription
):
    """Describe Matter binary sensor entities."""


class MatterBinarySensor(MatterEntity, BinarySensorEntity):
    """Representation of a Matter binary sensor."""

    entity_description: MatterBinarySensorEntityDescription

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        value: bool | uint | int | Nullable | None
        value = self.get_matter_attribute_value(self._entity_info.primary_attribute)
        if value in (None, NullValue):
            value = None
        elif value_convert := self.entity_description.measurement_to_ha:
            value = value_convert(value)
        self._attr_is_on = value


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    # device specific: translate Hue motion to sensor to HA Motion sensor
    # instead of generic occupancy sensor
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="HueMotionSensor",
            device_class=BinarySensorDeviceClass.MOTION,
            measurement_to_ha=lambda x: (x & 1 == 1) if x is not None else None,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.OccupancySensing.Attributes.Occupancy,),
        vendor_id=(4107,),
        product_name=("Hue motion sensor",),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="ContactSensor",
            device_class=BinarySensorDeviceClass.DOOR,
            # value is inverted on matter to what we expect
            measurement_to_ha=lambda x: not x,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.BooleanState.Attributes.StateValue,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="OccupancySensor",
            device_class=BinarySensorDeviceClass.OCCUPANCY,
            # The first bit = if occupied
            measurement_to_ha=lambda x: (x & 1 == 1) if x is not None else None,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.OccupancySensing.Attributes.Occupancy,),
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=MatterBinarySensorEntityDescription(
            key="BatteryChargeLevel",
            device_class=BinarySensorDeviceClass.BATTERY,
            entity_category=EntityCategory.DIAGNOSTIC,
            measurement_to_ha=lambda x: x
            != clusters.PowerSource.Enums.BatChargeLevelEnum.kOk,
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.PowerSource.Attributes.BatChargeLevel,),
        # only add binary battery sensor if a regular percentage based is not available
        absent_attributes=(clusters.PowerSource.Attributes.BatPercentRemaining,),
    ),
]
