"""Support for TPLink sensor entities."""

from __future__ import annotations

from typing import cast

from kasa import Device, Feature

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TPLinkConfigEntry
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import (
    CoordinatedTPLinkEntity,
    _description_for_feature,
    _entities_for_device_and_its_children,
)

UNIT_MAPPING = {
    "celsius": UnitOfTemperature.CELSIUS,
    "fahrenheit": UnitOfTemperature.FAHRENHEIT,
}


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

    entities = _entities_for_device_and_its_children(
        device=device,
        coordinator=parent_coordinator,
        feature_type=Feature.Type.Sensor,
        entity_class=Sensor,
        child_coordinators=children_coordinators,
    )
    async_add_entities(entities)


class Sensor(CoordinatedTPLinkEntity, SensorEntity):
    """Representation of a feature-based TPLink sensor."""

    def __init__(
        self,
        device: Device,
        coordinator: TPLinkDataUpdateCoordinator,
        *,
        feature: Feature,
        parent: Device | None = None,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = _description_for_feature(
            SensorEntityDescription, feature
        )
        super().__init__(device, coordinator, feature=feature, parent=parent)
        self._feature: Feature
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
