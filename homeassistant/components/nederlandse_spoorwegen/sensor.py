"""Support for Nederlandse Spoorwegen public transport."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NS sensors from config entry."""
    coordinator: NSDataUpdateCoordinator = config_entry.runtime_data

    # Wait for initial data
    if not coordinator.data:
        await coordinator.async_request_refresh()

    entities = []
    if coordinator.data and "routes" in coordinator.data:
        for route_key, route_data in coordinator.data["routes"].items():
            route = route_data["route"]
            entities.append(
                NSCoordinatorSensor(
                    coordinator=coordinator,
                    route_key=route_key,
                    route=route,
                )
            )

    async_add_entities(entities)


class NSCoordinatorSensor(CoordinatorEntity[NSDataUpdateCoordinator], SensorEntity):
    """Implementation of a NS sensor using coordinator."""

    _attr_attribution = "Data provided by NS"
    _attr_icon = "mdi:train"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NSDataUpdateCoordinator,
        route_key: str,
        route: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._route_key = route_key
        self._route = route
        self._attr_name = route[CONF_NAME]
        # Create a unique ID based on the route
        self._attr_unique_id = f"{DOMAIN}_{route_key}"

    @property
    def native_value(self) -> str | None:
        """Return the next departure time."""
        if not self.coordinator.data or "routes" not in self.coordinator.data:
            return None

        route_data = self.coordinator.data["routes"].get(self._route_key)
        if not route_data or not route_data.get("next_trip"):
            return None

        trip = route_data["next_trip"]
        if hasattr(trip, "departure_time_actual") and trip.departure_time_actual:
            return trip.departure_time_actual.strftime("%H:%M")

        if hasattr(trip, "departure_time_planned") and trip.departure_time_planned:
            return trip.departure_time_planned.strftime("%H:%M")

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if not self.coordinator.data or "routes" not in self.coordinator.data:
            return None

        route_data = self.coordinator.data["routes"].get(self._route_key)
        if not route_data:
            return None

        first_trip = route_data.get("next_trip")
        if not first_trip:
            return None

        attributes = {}

        # Trip information
        if hasattr(first_trip, "going"):
            attributes["going"] = first_trip.going

        # Departure times
        if hasattr(first_trip, "departure_time_planned"):
            attributes["departure_time_planned"] = first_trip.departure_time_planned
        if hasattr(first_trip, "departure_time_actual"):
            attributes["departure_time_actual"] = first_trip.departure_time_actual

        # Calculate delay
        if (
            hasattr(first_trip, "departure_time_planned")
            and hasattr(first_trip, "departure_time_actual")
            and first_trip.departure_time_planned
            and first_trip.departure_time_actual
        ):
            planned = first_trip.departure_time_planned
            actual = first_trip.departure_time_actual
            if planned != actual:
                delay = (actual - planned).total_seconds() / 60
                attributes["departure_delay"] = delay > 0
                attributes["departure_delay_minutes"] = int(delay)
            else:
                attributes["departure_delay"] = False
                attributes["departure_delay_minutes"] = 0
        else:
            attributes["departure_delay"] = False

        # Platform information
        if hasattr(first_trip, "departure_platform_planned"):
            attributes["departure_platform_planned"] = (
                first_trip.departure_platform_planned
            )
        if hasattr(first_trip, "departure_platform_actual"):
            attributes["departure_platform_actual"] = (
                first_trip.departure_platform_actual
            )

        # Route information
        attributes["route"] = self._route

        # All trips
        trips = route_data.get("trips", [])
        if trips:
            attributes["trips"] = [
                {
                    "departure_time_planned": getattr(
                        trip, "departure_time_planned", None
                    ),
                    "departure_time_actual": getattr(
                        trip, "departure_time_actual", None
                    ),
                    "departure_platform_planned": getattr(
                        trip, "departure_platform_planned", None
                    ),
                    "departure_platform_actual": getattr(
                        trip, "departure_platform_actual", None
                    ),
                    "status": getattr(trip, "status", None),
                }
                for trip in trips[:5]  # Limit to 5 upcoming trips
            ]

        return attributes


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform (legacy)."""
    _LOGGER.warning(
        "Platform-based configuration for Nederlandse Spoorwegen is no longer supported "
        "Please remove the 'nederlandse_spoorwegen' platform from your sensor configuration "
        "and set up the integration via the UI instead. Configuration via YAML has been "
        "automatically migrated to config entries"
    )
