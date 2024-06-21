"""Support for TPLink binary sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from kasa import Device, Feature

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TPLinkConfigEntry
from .coordinator import TPLinkDataUpdateCoordinator
from .entity import (
    CoordinatedTPLinkFeatureEntity,
    TPLinkFeatureEntityDescription,
    entities_for_device_and_its_children,
)


@dataclass(frozen=True, kw_only=True)
class TPLinkBinarySensorEntityDescription(
    BinarySensorEntityDescription, TPLinkFeatureEntityDescription
):
    """Base class for a TPLink feature based sensor entity description."""


BINARYSENSOR_DESCRIPTIONS: Final = (
    TPLinkBinarySensorEntityDescription(
        key="overheated",
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    TPLinkBinarySensorEntityDescription(
        key="battery_low",
        device_class=BinarySensorDeviceClass.BATTERY,
    ),
    TPLinkBinarySensorEntityDescription(
        key="cloud_connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    # To be replaced & disabled per default by the upcoming update platform.
    TPLinkBinarySensorEntityDescription(
        key="update_available",
        device_class=BinarySensorDeviceClass.UPDATE,
    ),
    TPLinkBinarySensorEntityDescription(
        key="temperature_warning",
    ),
    TPLinkBinarySensorEntityDescription(
        key="humidity_warning",
    ),
)

BINARYSENSOR_DESCRIPTIONS_MAP = {desc.key: desc for desc in BINARYSENSOR_DESCRIPTIONS}


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
        feature_type=Feature.Type.BinarySensor,
        entity_class=BinarySensor,
        child_coordinators=children_coordinators,
    )
    async_add_entities(entities)


class BinarySensor(CoordinatedTPLinkFeatureEntity, BinarySensorEntity):
    """Representation of a TPLink binary sensor."""

    entity_description: TPLinkBinarySensorEntityDescription

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
            TPLinkBinarySensorEntityDescription, feature, BINARYSENSOR_DESCRIPTIONS_MAP
        )
        super().__init__(
            device, coordinator, description=description, feature=feature, parent=parent
        )
        self._async_call_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity's attributes."""
        self._attr_is_on = self._feature.value
