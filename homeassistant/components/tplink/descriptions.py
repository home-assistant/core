"""Module containing entity descriptions for feature based platforms."""

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import TYPE_CHECKING

from kasa import Feature

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.const import (
    ATTR_VOLTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.helpers.entity import EntityDescription

from .const import (
    ATTR_CURRENT_A,
    ATTR_CURRENT_POWER_W,
    ATTR_TODAY_ENERGY_KWH,
    ATTR_TOTAL_ENERGY_KWH,
)

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)

# Mapping from upstream category to homeassistant category
FEATURE_CATEGORY_TO_ENTITY_CATEGORY = {
    Feature.Category.Config: EntityCategory.CONFIG,
    Feature.Category.Info: EntityCategory.DIAGNOSTIC,
    Feature.Category.Debug: EntityCategory.DIAGNOSTIC,
}


@dataclass(frozen=True)
class TPLinkFeatureEntityDescription(EntityDescription):
    """Describes TPLink entity."""

    feature_type: Feature.Type | None = None


@dataclass(frozen=True, kw_only=True)
class TPLinkSensorEntityDescription(
    SensorEntityDescription, TPLinkFeatureEntityDescription
):
    """Describes TPLink sensor entity."""

    feature_type: Feature.Type = Feature.Type.Sensor
    precision: int | None = None


@dataclass(frozen=True)
class TPLinkSwitchEntityDescription(
    SwitchEntityDescription, TPLinkFeatureEntityDescription
):
    """Describes TPLink switch entity."""

    feature_type: Feature.Type = Feature.Type.Switch


STATIC_DESCRIPTIONS: dict[str, TPLinkFeatureEntityDescription] = {
    "current_consumption": TPLinkSensorEntityDescription(
        key=ATTR_CURRENT_POWER_W,
        translation_key="current_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        precision=1,
    ),
    "consumption_total": TPLinkSensorEntityDescription(
        key=ATTR_TOTAL_ENERGY_KWH,
        translation_key="total_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        precision=3,
    ),
    "consumption_today": TPLinkSensorEntityDescription(
        key=ATTR_TODAY_ENERGY_KWH,
        translation_key="today_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        precision=3,
    ),
    "voltage": TPLinkSensorEntityDescription(
        key=ATTR_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        precision=1,
    ),
    "current": TPLinkSensorEntityDescription(
        key=ATTR_CURRENT_A,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        precision=2,
    ),
}


def _category_for_feature(feature: Feature | None) -> EntityCategory | None:
    """Return entity category for a feature."""
    # Main controls have no category
    if feature is None or feature.category is Feature.Category.Primary:
        return None

    if (
        entity_category := FEATURE_CATEGORY_TO_ENTITY_CATEGORY.get(feature.category)
    ) is None:
        _LOGGER.error("Unhandled category %s, fallback to DIAGNOSTIC", feature.category)
        entity_category = EntityCategory.DIAGNOSTIC

    return entity_category


def description_for_feature(feature: Feature) -> EntityDescription | None:
    """Return description object for the given feature.

    This is responsible for setting the common parameters & deciding based on feature id
    which additional parameters are passed.
    """

    if (
        description := STATIC_DESCRIPTIONS.get(feature.id)
    ) and description.feature_type == feature.type:
        return description

    if feature.type == Feature.Type.Sensor:
        if isinstance(feature.value, datetime):
            # Sensors need tzinfo for datetime values
            if feature.value.tzinfo is None:
                return None
            device_class = SensorDeviceClass.TIMESTAMP
            state_class = None
            native_unit_of_measurement = None
        else:
            device_class = None
            state_class = SensorStateClass.MEASUREMENT
            native_unit_of_measurement = feature.unit
        return TPLinkSensorEntityDescription(
            key=feature.id,
            name=feature.name,
            device_class=device_class,
            state_class=state_class,
            native_unit_of_measurement=native_unit_of_measurement,
            precision=feature.precision_hint,
            entity_registry_enabled_default=feature.category
            is not Feature.Category.Debug,
            entity_category=_category_for_feature(feature),
        )

    if feature.type == Feature.Type.Switch:
        return TPLinkSwitchEntityDescription(
            key=feature.id,
            name=feature.name,
            entity_registry_enabled_default=feature.category
            is not Feature.Category.Debug,
            entity_category=_category_for_feature(feature),
        )
    return None
