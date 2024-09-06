"""Support for TPLink sensor entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from kasa import Feature

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TPLinkConfigEntry
from .const import UNIT_MAPPING
from .entity import CoordinatedTPLinkFeatureEntity, TPLinkFeatureEntityDescription


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
        key="consumption_this_month",
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
    TPLinkSensorEntityDescription(
        # Disable as the value reported by the device changes seconds frequently
        entity_registry_enabled_default=False,
        key="on_since",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    TPLinkSensorEntityDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        key="signal_level",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        key="ssid",
    ),
    TPLinkSensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        key="auto_off_at",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    TPLinkSensorEntityDescription(
        key="device_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    TPLinkSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TPLinkSensorEntityDescription(
        key="report_interval",
        device_class=SensorDeviceClass.DURATION,
    ),
    TPLinkSensorEntityDescription(
        key="alarm_source",
    ),
    TPLinkSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
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

    entities = CoordinatedTPLinkFeatureEntity.entities_for_device_and_its_children(
        device=device,
        coordinator=parent_coordinator,
        feature_type=Feature.Type.Sensor,
        entity_class=TPLinkSensorEntity,
        descriptions=SENSOR_DESCRIPTIONS_MAP,
        child_coordinators=children_coordinators,
    )
    async_add_entities(entities)


class TPLinkSensorEntity(CoordinatedTPLinkFeatureEntity, SensorEntity):
    """Representation of a feature-based TPLink sensor."""

    entity_description: TPLinkSensorEntityDescription

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
        if (unit := self._feature.unit) is not None:
            self._attr_native_unit_of_measurement = UNIT_MAPPING.get(unit, unit)
