"""Support for TPLink sensor entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast

from kasa import Device, Feature

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_VOLTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_CURRENT_A,
    ATTR_CURRENT_POWER_W,
    ATTR_TODAY_ENERGY_KWH,
    ATTR_TOTAL_ENERGY_KWH,
    DOMAIN,
)
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import (
    DEVICETYPES_WITH_SPECIALIZED_PLATFORMS,
    CoordinatedTPLinkEntity,
    _category_for_feature,
)
from .models import TPLinkData


@dataclass(frozen=True)
class TPLinkSensorEntityDescription(SensorEntityDescription):
    """Describes TPLink sensor entity."""

    feature_id: str | None = None
    precision: int | None = None


ENERGY_SENSORS: tuple[TPLinkSensorEntityDescription, ...] = (
    TPLinkSensorEntityDescription(
        key=ATTR_CURRENT_POWER_W,
        translation_key="current_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        feature_id="current_consumption",
        precision=1,
    ),
    TPLinkSensorEntityDescription(
        key=ATTR_TOTAL_ENERGY_KWH,
        translation_key="total_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        feature_id="consumption_total",
        precision=3,
    ),
    TPLinkSensorEntityDescription(
        key=ATTR_TODAY_ENERGY_KWH,
        translation_key="today_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        feature_id="consumption_today",
        precision=3,
    ),
    TPLinkSensorEntityDescription(
        key=ATTR_VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        feature_id="voltage",
        precision=1,
    ),
    TPLinkSensorEntityDescription(
        key=ATTR_CURRENT_A,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        feature_id="current",
        precision=2,
    ),
)


def _new_sensor_description(feature: Feature) -> TPLinkSensorEntityDescription:
    """Create description for entities not yet added to the static description list."""
    if isinstance(feature.value, datetime):
        device_class = SensorDeviceClass.TIMESTAMP
    else:
        device_class = None
    return TPLinkSensorEntityDescription(
        key=feature.id,
        name=feature.name,
        native_unit_of_measurement=feature.unit,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=device_class,
        feature_id=feature.id,
        precision=feature.precision_hint,
        entity_registry_enabled_default=feature.category is not Feature.Category.Debug,
        entity_category=_category_for_feature(feature),
    )


def _async_sensors_for_device(
    device: Device,
    coordinator: TPLinkDataUpdateCoordinator,
    expected_features: set[str | None],
    parent: Device | None = None,
) -> list[CoordinatedTPLinkEntity]:
    """Generate the sensors for the device."""
    sensors: list[CoordinatedTPLinkEntity] = []

    sensors = [
        TPLinkSensor(
            device,
            coordinator,
            feature=device.features[description.feature_id],
            description=description,
            parent=parent,
        )
        for description in ENERGY_SENSORS
        if description.feature_id in device.features
    ]
    new_sensors: list[CoordinatedTPLinkEntity] = [
        TPLinkSensor(
            device,
            coordinator,
            feature=feat,
            description=_new_sensor_description(feat),
            parent=parent,
        )
        for feat in device.features.values()
        if feat.type == Feature.Sensor
        and feat.id not in expected_features
        # Timezone not currently supported in library
        and not isinstance(feat.value, datetime)
        and (
            feat.category != Feature.Category.Primary
            or device.device_type not in DEVICETYPES_WITH_SPECIALIZED_PLATFORMS
        )
    ]
    return sensors + new_sensors


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    data: TPLinkData = hass.data[DOMAIN][config_entry.entry_id]
    parent_coordinator = data.parent_coordinator
    children_coordinators = data.children_coordinators
    entities: list[CoordinatedTPLinkEntity] = []
    device = parent_coordinator.device
    expected_features = {description.feature_id for description in ENERGY_SENSORS}
    entities.extend(
        _async_sensors_for_device(
            device, parent_coordinator, expected_features=expected_features
        )
    )
    for idx, child in enumerate(device.children):
        # Only iot strips have child coordinators
        if children_coordinators:
            child_coordinator = children_coordinators[idx]
        else:
            child_coordinator = parent_coordinator
        entities.extend(
            _async_sensors_for_device(
                child,
                child_coordinator,
                expected_features=expected_features,
                parent=device,
            )
        )

    async_add_entities(entities)


class TPLinkSensor(CoordinatedTPLinkEntity, SensorEntity):
    """Representation of a feature-based TPLink sensor."""

    entity_description: TPLinkSensorEntityDescription

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        *,
        description: TPLinkSensorEntityDescription,
        feature: Feature,
        parent: Device | None = None,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(device, coordinator, feature=feature, parent=parent)
        self._feature: Feature
        self._async_call_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        value = self._feature.value
        if value is not None and self._feature.precision_hint is not None:
            value = round(cast(float, value), self._feature.precision_hint)
        self._attr_native_value = value
