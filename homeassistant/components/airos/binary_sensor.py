"""AirOS Binary Sensor component for Home Assistant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from airos.data import AirOSDataBaseClass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AirOS8Data, AirOSConfigEntry, AirOSDataUpdateCoordinator
from .entity import AirOSEntity

PARALLEL_UPDATES = 0

AirOSDataModel = TypeVar("AirOSDataModel", bound=AirOSDataBaseClass)


@dataclass(frozen=True, kw_only=True)
class AirOSBinarySensorEntityDescription(
    BinarySensorEntityDescription,
    Generic[AirOSDataModel],
):
    """Describe an AirOS binary sensor."""

    value_fn: Callable[[AirOSDataModel], bool]


AirOS8BinarySensorEntityDescription = AirOSBinarySensorEntityDescription[AirOS8Data]

COMMON_BINARY_SENSORS: tuple[AirOSBinarySensorEntityDescription, ...] = (
    AirOSBinarySensorEntityDescription(
        key="dhcp_client",
        translation_key="dhcp_client",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.services.dhcpc,
    ),
    AirOSBinarySensorEntityDescription(
        key="dhcp_server",
        translation_key="dhcp_server",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.services.dhcpd,
        entity_registry_enabled_default=False,
    ),
    AirOSBinarySensorEntityDescription(
        key="pppoe",
        translation_key="pppoe",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.services.pppoe,
        entity_registry_enabled_default=False,
    ),
)

AIROS8_BINARY_SENSORS: tuple[AirOS8BinarySensorEntityDescription, ...] = (
    AirOS8BinarySensorEntityDescription(
        key="portfw",
        translation_key="port_forwarding",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.portfw,
    ),
    AirOS8BinarySensorEntityDescription(
        key="dhcp6_server",
        translation_key="dhcp6_server",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.services.dhcp6d_stateful,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AirOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AirOS binary sensors from a config entry."""
    coordinator = config_entry.runtime_data

    entities = [
        AirOSBinarySensor(coordinator, description)
        for description in COMMON_BINARY_SENSORS
    ]

    if coordinator.device_data["fw_major"] == 8:
        entities.extend(
            AirOSBinarySensor(coordinator, description)
            for description in AIROS8_BINARY_SENSORS
        )

    async_add_entities(entities)


class AirOSBinarySensor(AirOSEntity, BinarySensorEntity):
    """Representation of a binary sensor."""

    entity_description: AirOSBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: AirOSDataUpdateCoordinator,
        description: AirOSBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.derived.mac}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
