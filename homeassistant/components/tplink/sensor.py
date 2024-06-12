"""Support for TPLink sensor entities."""

from __future__ import annotations

from typing import cast

from kasa import Device, Feature
from kasa.iot import IotBulb

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_VOLTAGE
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
    CoordinatedTPLinkEntity,
    _description_for_feature,
    _entities_for_device_and_its_children,
)
from .models import TPLinkData

EMETER_FEATURE_IDS = {
    ATTR_CURRENT_POWER_W,
    ATTR_TOTAL_ENERGY_KWH,
    ATTR_VOLTAGE,
    ATTR_CURRENT_A,
}

FEATURE_INFO: dict[str, dict] = {
    ATTR_CURRENT_POWER_W: {
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "translation_key": "current_consumption",
    },
    ATTR_TOTAL_ENERGY_KWH: {
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "translation_key": "total_consumption",
    },
    ATTR_TODAY_ENERGY_KWH: {
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "translation_key": "today_consumption",
    },
    ATTR_VOLTAGE: {
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    ATTR_CURRENT_A: {
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
}


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

    entities.extend(
        _entities_for_device_and_its_children(
            device,
            feature_type=Feature.Sensor,
            entity_class=TPLinkSensor,
            coordinator=parent_coordinator,
            extra_filter=_sensor_filter,
            children_coordinators=children_coordinators,
        )
    )

    async_add_entities(entities)


def _sensor_filter(device: Device, feature: Feature) -> bool:
    "Filter sensors."
    # today's consumption not available, when device was off all the day
    if feature.id == ATTR_TODAY_ENERGY_KWH:
        # iot bulb's do not report this information, so filter it out
        if isinstance(device, IotBulb):
            return False
        return True
    # By default do not show emeter features with None values
    if feature.id in EMETER_FEATURE_IDS:
        return feature.value is not None
    return True


class TPLinkSensor(CoordinatedTPLinkEntity, SensorEntity):
    """Representation of a feature-based TPLink sensor."""

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        feature: Feature,
        parent: Device | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, coordinator, feature=feature, parent=parent)
        self._feature: Feature
        feature_info = FEATURE_INFO.get(feature.id, {})
        self.entity_description = _description_for_feature(
            SensorEntityDescription,
            feature,
            native_unit_of_measurement=feature.unit,
            **feature_info,
        )
        self._async_call_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        value = self._feature.value
        if value is not None and self._feature.precision_hint is not None:
            value = round(cast(float, value), self._feature.precision_hint)
        # today's consumption not available, when device was off all the day
        # so show it as zero
        if self._feature.id == ATTR_TODAY_ENERGY_KWH and value is None:
            value = 0.0
        self._attr_native_value = value
