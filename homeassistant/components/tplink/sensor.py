"""Support for TPLink sensor entities."""

from __future__ import annotations

from typing import cast

from kasa import Device, Feature

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TPLinkConfigEntry
from .coordinator import TPLinkDataUpdateCoordinator
from .descriptions import TPLinkSensorEntityDescription
from .entity import CoordinatedTPLinkEntity, _entities_for_device_and_its_children


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    children_coordinators = data.children_coordinators
    entities: list[CoordinatedTPLinkEntity] = []
    device = parent_coordinator.device

    entities = _entities_for_device_and_its_children(
        device=device,
        coordinator=parent_coordinator,
        feature_type=Feature.Type.Sensor,
        entity_class=TPLinkSensor,
        child_coordinators=children_coordinators,
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
        super().__init__(
            device, coordinator, description=description, feature=feature, parent=parent
        )
        self._feature: Feature
        self._async_call_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        value = self._feature.value
        if value is not None and self._feature.precision_hint is not None:
            value = round(cast(float, value), self._feature.precision_hint)
        self._attr_native_value = value
