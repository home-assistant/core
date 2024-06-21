"""Support for TPLink sensor entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from kasa import Device, Feature

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TPLinkConfigEntry
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import (
    CoordinatedTPLinkFeatureEntity,
    TPLinkFeatureEntityDescription,
    entities_for_device_and_its_children,
)

UNIT_MAPPING = {
    "celsius": UnitOfTemperature.CELSIUS,
    "fahrenheit": UnitOfTemperature.FAHRENHEIT,
}


@dataclass(frozen=True, kw_only=True)
class TPLinkSensorEntityDescription(
    SensorEntityDescription, TPLinkFeatureEntityDescription
):
    """Base class for a TPLink feature based sensor entity description."""


SENSOR_DESCRIPTIONS: tuple[TPLinkSensorEntityDescription, ...] = (
    TPLinkSensorEntityDescription(
        key="current_consumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        key="consumption_total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    TPLinkSensorEntityDescription(
        key="consumption_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    TPLinkSensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

SENSOR_DESCRIPTIONS_MAP = {desc.key: desc for desc in SENSOR_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    children_coordinators = data.children_coordinators
    device = parent_coordinator.device

    entities = entities_for_device_and_its_children(
        device=device,
        coordinator=parent_coordinator,
        feature_type=Feature.Type.Sensor,
        entity_class=Sensor,
        child_coordinators=children_coordinators,
    )
    async_add_entities(entities)


class Sensor(CoordinatedTPLinkFeatureEntity, SensorEntity):
    """Representation of a feature-based TPLink sensor."""

    entity_description: TPLinkSensorEntityDescription

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        *,
        feature: Feature,
        parent: Device | None = None,
    ) -> None:
        """Initialize the sensor."""
        description = self._description_for_feature(
            TPLinkSensorEntityDescription, feature, SENSOR_DESCRIPTIONS_MAP
        )
        super().__init__(
            device, coordinator, description=description, feature=feature, parent=parent
        )
        self._async_call_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        value = self._feature.value
        if value is not None and self._feature.precision_hint is not None:
            value = round(cast(float, value), self._feature.precision_hint)
            # We probably do not need this, when we are rounding already?
            self._attr_suggested_display_precision = self._feature.precision_hint

        self._attr_native_value = value
        # Map to homeassistant units and fallback to upstream one if none found
        if self._feature.unit is not None:
            self._attr_native_unit_of_measurement = UNIT_MAPPING.get(
                self._feature.unit, self._feature.unit
            )
