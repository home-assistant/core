"""Support for the NextDNS service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nextdns import ConnectionStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NextDnsConfigEntry
from .entity import NextDnsEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class NextDnsBinarySensorEntityDescription(BinarySensorEntityDescription):
    """NextDNS binary sensor entity description."""

    state: Callable[[ConnectionStatus, str], bool]


SENSORS = (
    NextDnsBinarySensorEntityDescription(
        key="this_device_nextdns_connection_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="device_connection_status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        state=lambda data, _: data.connected,
    ),
    NextDnsBinarySensorEntityDescription(
        key="this_device_profile_connection_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="device_profile_connection_status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        state=lambda data, profile_id: profile_id == data.profile_id,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NextDnsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add NextDNS entities from a config_entry."""
    coordinator = entry.runtime_data.connection

    async_add_entities(
        NextDnsBinarySensor(coordinator, description) for description in SENSORS
    )


class NextDnsBinarySensor(NextDnsEntity, BinarySensorEntity):
    """Define an NextDNS binary sensor."""

    entity_description: NextDnsBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return self.entity_description.state(
            self.coordinator.data, self.coordinator.profile_id
        )
