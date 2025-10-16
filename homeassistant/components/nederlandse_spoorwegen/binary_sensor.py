"""Support for Nederlandse Spoorwegen public transport."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_API_KEY, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ROUTES, DOMAIN, INTEGRATION_TITLE, ROUTE_MODEL, ROUTES_SCHEMA
from .coordinator import NSConfigEntry, NSDataUpdateCoordinator
from .utils import (
    get_arrival_delay,
    get_coordinator_data_attribute,
    get_departure_delay,
    get_going,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0  # since we use coordinator pattern

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_API_KEY): cv.string, vol.Optional(CONF_ROUTES): ROUTES_SCHEMA}
)


@dataclass(frozen=True, kw_only=True)
class NSSensorEntityDescription(BinarySensorEntityDescription):
    """Describes Nederlandse Spoorwegen sensor entity."""

    entity_category: EntityCategory | None = None
    data_fn: Callable[[Any], Any] | None = None
    value_fn: Callable[[Any], Any] | None = None


BINARY_SENSOR_DESCRIPTIONS = [
    NSSensorEntityDescription(
        key="is_departure_delayed",
        translation_key="is_departure_delayed",
        name="Departure delayed",
        icon="mdi:bell-alert-outline",
        data_fn=lambda coordinator: get_coordinator_data_attribute(
            coordinator, "first_trip"
        ),
        value_fn=get_departure_delay,
    ),
    NSSensorEntityDescription(
        key="is_arrival_delayed",
        translation_key="is_arrival_delayed",
        name="Arrival delayed",
        icon="mdi:bell-alert-outline",
        data_fn=lambda coordinator: get_coordinator_data_attribute(
            coordinator, "first_trip"
        ),
        value_fn=get_arrival_delay,
    ),
    NSSensorEntityDescription(
        key="is_going",
        translation_key="is_going",
        name="Going",
        icon="mdi:bell-cancel-outline",
        data_fn=lambda coordinator: get_coordinator_data_attribute(
            coordinator, "first_trip"
        ),
        value_fn=get_going,
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
        subentry_entities: list[BinarySensorEntity] = []
        # Build entity from coordinator fields directly
        subentry_entities.extend(
            [
                NSBinarySensor(coordinator, subentry_id, description)
                for description in BINARY_SENSOR_DESCRIPTIONS
            ]
        )

        # Add all entities for this subentry
        async_add_entities(subentry_entities, config_subentry_id=subentry_id)


class NSBinarySensor(CoordinatorEntity[NSDataUpdateCoordinator], BinarySensorEntity):
    """Generic NS binary sensor based on entity description."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by NS"
    entity_description: NSSensorEntityDescription

    def __init__(
        self,
        coordinator: NSDataUpdateCoordinator,
        subentry_id: str,
        description: NSSensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._subentry_id = subentry_id

        self._attr_unique_id = f"{subentry_id}-{description.key}"
        self._attr_entity_category = description.entity_category
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=coordinator.name,
            manufacturer=INTEGRATION_TITLE,
            model=ROUTE_MODEL,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if (
            not self.coordinator
            or not self.coordinator.data
            or not self.entity_description.value_fn
        ):
            return None

        data = (
            self.entity_description.data_fn(self.coordinator)
            if self.entity_description.data_fn
            else None
        )
        if data is None:
            return None
        value = self.entity_description.value_fn(data)
        # Accept bool, or interpret truthy/falsy values
        if isinstance(value, bool):
            return value
        return bool(value)
