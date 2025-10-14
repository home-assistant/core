"""AirOS Binary Sensor component for Home Assistant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

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

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirOSBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe an AirOS binary sensor."""

    value_fn: Callable[[AirOS8Data], bool]


BINARY_SENSORS: tuple[AirOSBinarySensorEntityDescription, ...] = (
    AirOSBinarySensorEntityDescription(
        key="portfw",
        translation_key="port_forwarding",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.portfw,
    ),
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
        key="dhcp6_server",
        translation_key="dhcp6_server",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.services.dhcp6d_stateful,
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AirOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AirOS binary sensors from a config entry."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        AirOSBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


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
