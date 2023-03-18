"""Matter binary sensors."""
from __future__ import annotations

from chip.clusters import Objects as clusters
from chip.clusters.Objects import uint
from chip.clusters.Types import Nullable, NullValue

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
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
    """Set up Matter binary sensor from Config Entry."""
    matter = get_matter(hass)
    matter.register_platform_handler(Platform.BINARY_SENSOR, async_add_entities)


class MatterBinarySensor(MatterEntity, BinarySensorEntity):
    """Representation of a Matter binary sensor."""

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        value: bool | uint | int | Nullable | None
        value = self.get_matter_attribute_value(self._entity_info.primary_attribute)
        if value in (None, NullValue):
            value = None
        elif value_convert := self._entity_info.measurement_to_ha:
            value = value_convert(value)
        self._attr_is_on = value


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    # device specific: translate Hue motion to sensor to HA Motion sensor
    # instead of generic occupancy sensor
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=BinarySensorEntityDescription(
            key="HueMotionSensor",
            device_class=BinarySensorDeviceClass.MOTION,
            name="Motion",
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.OccupancySensing.Attributes.Occupancy,),
        vendor_id=(4107,),
        product_name=("Hue motion sensor",),
        measurement_to_ha=lambda x: (x & 1 == 1) if x is not None else None,
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=BinarySensorEntityDescription(
            key="ContactSensor",
            device_class=BinarySensorDeviceClass.DOOR,
            name="Contact",
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.BooleanState.Attributes.StateValue,),
        # value is inverted on matter to what we expect
        measurement_to_ha=lambda x: not x,
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=BinarySensorEntityDescription(
            key="OccupancySensor",
            device_class=BinarySensorDeviceClass.OCCUPANCY,
            name="Occupancy",
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.OccupancySensing.Attributes.Occupancy,),
        # The first bit = if occupied
        measurement_to_ha=lambda x: (x & 1 == 1) if x is not None else None,
    ),
    MatterDiscoverySchema(
        platform=Platform.BINARY_SENSOR,
        entity_description=BinarySensorEntityDescription(
            key="BatteryChargeLevel",
            device_class=BinarySensorDeviceClass.BATTERY,
            name="Battery Status",
        ),
        entity_class=MatterBinarySensor,
        required_attributes=(clusters.PowerSource.Attributes.BatChargeLevel,),
        # only add binary battery sensor if a regular percentage based is not available
        absent_attributes=(clusters.PowerSource.Attributes.BatPercentRemaining,),
        measurement_to_ha=lambda x: x != clusters.PowerSource.Enums.BatChargeLevel.kOk,
    ),
]
