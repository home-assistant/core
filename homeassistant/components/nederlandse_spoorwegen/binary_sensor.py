"""Support for Nederlandse Spoorwegen public transport."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging

from ns_api import Trip

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, INTEGRATION_TITLE, ROUTE_MODEL
from .coordinator import NSConfigEntry, NSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0  # since we use coordinator pattern


@dataclass(frozen=True, kw_only=True)
class NSBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Nederlandse Spoorwegen sensor entity."""

    value_fn: Callable[[Trip], bool]


def get_delay(planned: datetime | None, actual: datetime | None) -> bool:
    """Return True if delay is present, False otherwise."""
    return bool(planned and actual and planned != actual)


BINARY_SENSOR_DESCRIPTIONS = [
    NSBinarySensorEntityDescription(
        key="is_departure_delayed",
        translation_key="is_departure_delayed",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda trip: get_delay(
            trip.departure_time_planned, trip.departure_time_actual
        ),
        entity_registry_enabled_default=False,
    ),
    NSBinarySensorEntityDescription(
        key="is_arrival_delayed",
        translation_key="is_arrival_delayed",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda trip: get_delay(
            trip.arrival_time_planned, trip.arrival_time_actual
        ),
        entity_registry_enabled_default=False,
    ),
    NSBinarySensorEntityDescription(
        key="is_going",
        translation_key="is_going",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda trip: trip.going,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the departure sensor from a config entry."""

    coordinators = config_entry.runtime_data

    for subentry_id, coordinator in coordinators.items():
        async_add_entities(
            (
                NSBinarySensor(coordinator, subentry_id, description)
                for description in BINARY_SENSOR_DESCRIPTIONS
            ),
            config_subentry_id=subentry_id,
        )


class NSBinarySensor(CoordinatorEntity[NSDataUpdateCoordinator], BinarySensorEntity):
    """Generic NS binary sensor based on entity description."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by NS"
    entity_description: NSBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: NSDataUpdateCoordinator,
        subentry_id: str,
        description: NSBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._subentry_id = subentry_id
        self._attr_unique_id = f"{subentry_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=coordinator.name,
            manufacturer=INTEGRATION_TITLE,
            model=ROUTE_MODEL,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not (trip := self.coordinator.data.first_trip):
            return None
        return self.entity_description.value_fn(trip)
