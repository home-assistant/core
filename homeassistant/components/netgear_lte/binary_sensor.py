"""Support for Netgear LTE binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NetgearLTEConfigEntry
from .entity import LTEEntity

BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="roaming",
        translation_key="roaming",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="wire_connected",
        translation_key="wire_connected",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinarySensorEntityDescription(
        key="mobile_connected",
        translation_key="mobile_connected",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetgearLTEConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Netgear LTE binary sensor."""
    async_add_entities(
        NetgearLTEBinarySensor(entry, description) for description in BINARY_SENSORS
    )


class NetgearLTEBinarySensor(LTEEntity, BinarySensorEntity):
    """Netgear LTE binary sensor entity."""

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return getattr(self.coordinator.data, self.entity_description.key)
