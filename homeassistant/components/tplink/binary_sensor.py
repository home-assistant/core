"""Support for TPLink binary sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from kasa import Feature

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TPLinkConfigEntry
from .entity import CoordinatedTPLinkFeatureEntity, TPLinkFeatureEntityDescription


@dataclass(frozen=True, kw_only=True)
class TPLinkBinarySensorEntityDescription(
    BinarySensorEntityDescription, TPLinkFeatureEntityDescription
):
    """Base class for a TPLink feature based binary sensor entity description."""


# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

BINARY_SENSOR_DESCRIPTIONS: Final = (
    TPLinkBinarySensorEntityDescription(
        key="overheated",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    TPLinkBinarySensorEntityDescription(
        key="overloaded",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    TPLinkBinarySensorEntityDescription(
        key="battery_low",
        device_class=BinarySensorDeviceClass.BATTERY,
    ),
    TPLinkBinarySensorEntityDescription(
        key="cloud_connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    TPLinkBinarySensorEntityDescription(
        key="temperature_warning",
    ),
    TPLinkBinarySensorEntityDescription(
        key="humidity_warning",
    ),
    TPLinkBinarySensorEntityDescription(
        key="is_open",
        device_class=BinarySensorDeviceClass.DOOR,
    ),
    TPLinkBinarySensorEntityDescription(
        key="water_alert",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    TPLinkBinarySensorEntityDescription(
        key="motion_detected",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
)

BINARYSENSOR_DESCRIPTIONS_MAP = {desc.key: desc for desc in BINARY_SENSOR_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TPLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    data = config_entry.runtime_data
    parent_coordinator = data.parent_coordinator
    device = parent_coordinator.device

    known_child_device_ids: set[str] = set()
    first_check = True

    def _check_device() -> None:
        entities = CoordinatedTPLinkFeatureEntity.entities_for_device_and_its_children(
            hass=hass,
            device=device,
            coordinator=parent_coordinator,
            feature_type=Feature.Type.BinarySensor,
            entity_class=TPLinkBinarySensorEntity,
            descriptions=BINARYSENSOR_DESCRIPTIONS_MAP,
            platform_domain=BINARY_SENSOR_DOMAIN,
            known_child_device_ids=known_child_device_ids,
            first_check=first_check,
        )
        async_add_entities(entities)

    _check_device()
    first_check = False
    config_entry.async_on_unload(parent_coordinator.async_add_listener(_check_device))


class TPLinkBinarySensorEntity(CoordinatedTPLinkFeatureEntity, BinarySensorEntity):
    """Representation of a TPLink binary sensor."""

    entity_description: TPLinkBinarySensorEntityDescription

    @callback
    def _async_update_attrs(self) -> bool:
        """Update the entity's attributes."""
        self._attr_is_on = cast(bool | None, self._feature.value)
        return True
