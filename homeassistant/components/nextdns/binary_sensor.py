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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NextDnsConfigEntry
from .coordinator import NextDnsUpdateCoordinator
from .entity import NextDnsEntity, NextDnsEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class NextDnsBinarySensorEntityDescription(
    NextDnsEntityDescription, BinarySensorEntityDescription
):
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

    def __init__(
        self,
        coordinator: NextDnsUpdateCoordinator[ConnectionStatus],
        description: NextDnsBinarySensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, description)
        self._attr_is_on = description.state(coordinator.data, coordinator.profile_id)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.entity_description.state(
            self.coordinator.data, self.coordinator.profile_id
        )
        self.async_write_ha_state()
