"""Support for monitoring OpenEVSE Charger binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from openevsehttp.__main__ import OpenEVSE

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import ATTR_CONNECTIONS, ATTR_SERIAL_NUMBER, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OpenEVSEConfigEntry, OpenEVSEDataUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OpenEVSEBinarySensorDescription(BinarySensorEntityDescription):
    """Describes an OpenEVSE binary sensor entity."""

    value_fn: Callable[[OpenEVSE], bool | None]


BINARY_SENSOR_TYPES: tuple[OpenEVSEBinarySensorDescription, ...] = (
    OpenEVSEBinarySensorDescription(
        key="vehicle",
        translation_key="vehicle",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda ev: ev.vehicle,
    ),
    OpenEVSEBinarySensorDescription(
        key="divert_active",
        translation_key="divert_active",
        value_fn=lambda ev: ev.divert_active,
    ),
    OpenEVSEBinarySensorDescription(
        key="using_ethernet",
        translation_key="using_ethernet",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.using_ethernet,
    ),
    OpenEVSEBinarySensorDescription(
        key="shaper_active",
        translation_key="shaper_active",
        value_fn=lambda ev: ev.shaper_active,
    ),
    OpenEVSEBinarySensorDescription(
        key="has_limit",
        translation_key="has_limit",
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.has_limit,
    ),
    OpenEVSEBinarySensorDescription(
        key="mqtt_connected",
        translation_key="mqtt_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda ev: ev.mqtt_connected,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenEVSEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenEVSE binary sensors based on config entry."""
    coordinator = entry.runtime_data
    identifier = entry.unique_id or entry.entry_id
    async_add_entities(
        OpenEVSEBinarySensor(coordinator, description, identifier, entry.unique_id)
        for description in BINARY_SENSOR_TYPES
    )


class OpenEVSEBinarySensor(
    CoordinatorEntity[OpenEVSEDataUpdateCoordinator], BinarySensorEntity
):
    """Implementation of an OpenEVSE binary sensor."""

    _attr_has_entity_name = True
    entity_description: OpenEVSEBinarySensorDescription

    def __init__(
        self,
        coordinator: OpenEVSEDataUpdateCoordinator,
        description: OpenEVSEBinarySensorDescription,
        identifier: str,
        unique_id: str | None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{identifier}-{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer="OpenEVSE",
        )
        if unique_id:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (CONNECTION_NETWORK_MAC, unique_id)
            }
            self._attr_device_info[ATTR_SERIAL_NUMBER] = unique_id

    @property
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.charger)
