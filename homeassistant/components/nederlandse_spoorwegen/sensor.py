"""Support for Nederlandse Spoorwegen public transport."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NSConfigEntry
from .api import get_ns_api_version
from .const import CONF_FROM, CONF_TO, CONF_VIA, DOMAIN
from .coordinator import NSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NS sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator
    if coordinator is None:
        _LOGGER.error("Coordinator not found in runtime_data for NS integration")
        return
    _LOGGER.debug(
        "NS sensor setup: coordinator=%s, entry_id=%s", coordinator, entry.entry_id
    )

    # No entities created for main entry - all entities are created under subentries

    # Handle subentry routes - create entities under each subentry
    for subentry_id, subentry in entry.subentries.items():
        subentry_entities: list[SensorEntity] = []
        subentry_data = subentry.data

        # Create route sensor for this subentry
        route = {
            CONF_NAME: subentry_data.get(CONF_NAME, subentry.title),
            CONF_FROM: subentry_data[CONF_FROM],
            CONF_TO: subentry_data[CONF_TO],
            CONF_VIA: subentry_data.get(CONF_VIA),
            "route_id": subentry_id,
        }

        _LOGGER.debug(
            "Creating sensors for subentry route %s (subentry_id: %s)",
            route[CONF_NAME],
            subentry_id,
        )

        # Platform sensors
        subentry_entities.extend(
            [
                NSDeparturePlatformPlannedSensor(
                    coordinator, entry, route, subentry_id
                ),
                NSDeparturePlatformActualSensor(coordinator, entry, route, subentry_id),
                NSArrivalPlatformPlannedSensor(coordinator, entry, route, subentry_id),
                NSArrivalPlatformActualSensor(coordinator, entry, route, subentry_id),
            ]
        )

        # Time sensors
        subentry_entities.extend(
            [
                NSDepartureTimePlannedSensor(coordinator, entry, route, subentry_id),
                NSDepartureTimeActualSensor(coordinator, entry, route, subentry_id),
                NSArrivalTimePlannedSensor(coordinator, entry, route, subentry_id),
                NSArrivalTimeActualSensor(coordinator, entry, route, subentry_id),
                NSNextDepartureSensor(coordinator, entry, route, subentry_id),
            ]
        )

        # Status sensors
        subentry_entities.extend(
            [
                NSStatusSensor(coordinator, entry, route, subentry_id),
                NSTransfersSensor(coordinator, entry, route, subentry_id),
            ]
        )

        # Route info sensors (static but useful for automation)
        subentry_entities.extend(
            [
                NSRouteFromSensor(coordinator, entry, route, subentry_id),
                NSRouteToSensor(coordinator, entry, route, subentry_id),
                NSRouteViaSensor(coordinator, entry, route, subentry_id),
            ]
        )

        # Add subentry entities with proper config_subentry_id
        async_add_entities(subentry_entities, config_subentry_id=subentry_id)


# Base class for NS attribute sensors
class NSAttributeSensorBase(CoordinatorEntity[NSDataUpdateCoordinator], SensorEntity):
    """Base class for NS attribute sensors."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by NS"

    def __init__(
        self,
        coordinator: NSDataUpdateCoordinator,
        entry: NSConfigEntry,
        route: dict[str, Any],
        route_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._route = route
        self._route_key = route_key

        # Check if this is a subentry route
        if route.get("route_id") and route["route_id"] in entry.subentries:
            # For subentry routes, create a unique device per route
            subentry_id = route["route_id"]
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, subentry_id)},
                name=route[CONF_NAME],
                manufacturer="Nederlandse Spoorwegen",
                model="NS Route",
                sw_version=get_ns_api_version(),
                configuration_url="https://www.ns.nl/",
            )
        else:
            # For legacy routes, use the main integration device
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, entry.entry_id)},
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._route_key in self.coordinator.data.get("routes", {})
        )

    def _get_first_trip(self):
        """Get the first trip data."""
        if not self.coordinator.data:
            return None
        route_data = self.coordinator.data.get("routes", {}).get(self._route_key, {})
        return route_data.get("first_trip")

    def _get_next_trip(self):
        """Get the next trip data."""
        if not self.coordinator.data:
            return None
        route_data = self.coordinator.data.get("routes", {}).get(self._route_key, {})
        return route_data.get("next_trip")


# Platform sensors
class NSDeparturePlatformPlannedSensor(NSAttributeSensorBase):
    """Sensor for departure platform planned."""

    _attr_translation_key = "departure_platform_planned"

    def __init__(self, coordinator, entry, route, route_key) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, route, route_key)
        self._attr_unique_id = f"{route_key}_departure_platform_planned"
        self._attr_name = "Departure platform planned"

    @property
    def native_value(self) -> str | None:
        """Return the departure platform planned."""
        first_trip = self._get_first_trip()
        if first_trip:
            return getattr(first_trip, "departure_platform_planned", None)
        return None


class NSDeparturePlatformActualSensor(NSAttributeSensorBase):
    """Sensor for departure platform actual."""

    _attr_translation_key = "departure_platform_actual"

    def __init__(self, coordinator, entry, route, route_key) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, route, route_key)
        self._attr_unique_id = f"{route_key}_departure_platform_actual"
        self._attr_name = "Departure platform actual"

    @property
    def native_value(self) -> str | None:
        """Return the departure platform actual."""
        first_trip = self._get_first_trip()
        if first_trip:
            return getattr(first_trip, "departure_platform_actual", None)
        return None


class NSArrivalPlatformPlannedSensor(NSAttributeSensorBase):
    """Sensor for arrival platform planned."""

    _attr_translation_key = "arrival_platform_planned"

    def __init__(self, coordinator, entry, route, route_key) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, route, route_key)
        self._attr_unique_id = f"{route_key}_arrival_platform_planned"
        self._attr_name = "Arrival platform planned"

    @property
    def native_value(self) -> str | None:
        """Return the arrival platform planned."""
        first_trip = self._get_first_trip()
        if first_trip:
            return getattr(first_trip, "arrival_platform_planned", None)
        return None


class NSArrivalPlatformActualSensor(NSAttributeSensorBase):
    """Sensor for arrival platform actual."""

    _attr_translation_key = "arrival_platform_actual"

    def __init__(self, coordinator, entry, route, route_key) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, route, route_key)
        self._attr_unique_id = f"{route_key}_arrival_platform_actual"
        self._attr_name = "Arrival platform actual"

    @property
    def native_value(self) -> str | None:
        """Return the arrival platform actual."""
        first_trip = self._get_first_trip()
        if first_trip:
            return getattr(first_trip, "arrival_platform_actual", None)
        return None


# Time sensors
class NSDepartureTimePlannedSensor(NSAttributeSensorBase):
    """Sensor for departure time planned."""

    _attr_translation_key = "departure_time_planned"

    def __init__(self, coordinator, entry, route, route_key) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, route, route_key)
        self._attr_unique_id = f"{route_key}_departure_time_planned"
        self._attr_name = "Departure time planned"

    @property
    def native_value(self) -> str | None:
        """Return the departure time planned."""
        first_trip = self._get_first_trip()
        if first_trip:
            departure_planned = getattr(first_trip, "departure_time_planned", None)
            if departure_planned and isinstance(departure_planned, datetime):
                return departure_planned.strftime("%H:%M")
        return None


class NSDepartureTimeActualSensor(NSAttributeSensorBase):
    """Sensor for departure time actual."""

    _attr_translation_key = "departure_time_actual"

    def __init__(self, coordinator, entry, route, route_key) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, route, route_key)
        self._attr_unique_id = f"{route_key}_departure_time_actual"
        self._attr_name = "Departure time actual"

    @property
    def native_value(self) -> str | None:
        """Return the departure time actual."""
        first_trip = self._get_first_trip()
        if first_trip:
            departure_actual = getattr(first_trip, "departure_time_actual", None)
            if departure_actual and isinstance(departure_actual, datetime):
                return departure_actual.strftime("%H:%M")
        return None


class NSArrivalTimePlannedSensor(NSAttributeSensorBase):
    """Sensor for arrival time planned."""

    _attr_translation_key = "arrival_time_planned"

    def __init__(self, coordinator, entry, route, route_key) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, route, route_key)
        self._attr_unique_id = f"{route_key}_arrival_time_planned"
        self._attr_name = "Arrival time planned"

    @property
    def native_value(self) -> str | None:
        """Return the arrival time planned."""
        first_trip = self._get_first_trip()
        if first_trip:
            arrival_planned = getattr(first_trip, "arrival_time_planned", None)
            if arrival_planned and isinstance(arrival_planned, datetime):
                return arrival_planned.strftime("%H:%M")
        return None


class NSArrivalTimeActualSensor(NSAttributeSensorBase):
    """Sensor for arrival time actual."""

    _attr_translation_key = "arrival_time_actual"

    def __init__(self, coordinator, entry, route, route_key) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, route, route_key)
        self._attr_unique_id = f"{route_key}_arrival_time_actual"
        self._attr_name = "Arrival time actual"

    @property
    def native_value(self) -> str | None:
        """Return the arrival time actual."""
        first_trip = self._get_first_trip()
        if first_trip:
            arrival_actual = getattr(first_trip, "arrival_time_actual", None)
            if arrival_actual and isinstance(arrival_actual, datetime):
                return arrival_actual.strftime("%H:%M")
        return None


class NSNextDepartureSensor(NSAttributeSensorBase):
    """Sensor for next departure time."""

    _attr_translation_key = "next_departure"

    def __init__(self, coordinator, entry, route, route_key) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, route, route_key)
        self._attr_unique_id = f"{route_key}_next_departure"
        self._attr_name = "Next departure"

    @property
    def native_value(self) -> str | None:
        """Return the next departure time."""
        next_trip = self._get_next_trip()
        if next_trip:
            next_departure = getattr(
                next_trip, "departure_time_actual", None
            ) or getattr(next_trip, "departure_time_planned", None)
            if next_departure and isinstance(next_departure, datetime):
                return next_departure.strftime("%H:%M")
        return None


# Status sensors
class NSStatusSensor(NSAttributeSensorBase):
    """Sensor for trip status."""

    _attr_translation_key = "status"

    def __init__(self, coordinator, entry, route, route_key) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, route, route_key)
        self._attr_unique_id = f"{route_key}_status"
        self._attr_name = "Status"

    @property
    def native_value(self) -> str | None:
        """Return the trip status."""
        first_trip = self._get_first_trip()
        if first_trip:
            return getattr(first_trip, "status", None)
        return None


class NSTransfersSensor(NSAttributeSensorBase):
    """Sensor for number of transfers."""

    _attr_translation_key = "transfers"

    def __init__(self, coordinator, entry, route, route_key) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, route, route_key)
        self._attr_unique_id = f"{route_key}_transfers"
        self._attr_name = "Transfers"

    @property
    def native_value(self) -> int | None:
        """Return the number of transfers."""
        first_trip = self._get_first_trip()
        if first_trip:
            return getattr(first_trip, "nr_transfers", None)
        return None


# Route info sensors (static but useful for automation)
class NSRouteFromSensor(NSAttributeSensorBase):
    """Sensor for route from station."""

    _attr_translation_key = "route_from"

    def __init__(self, coordinator, entry, route, route_key) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, route, route_key)
        self._attr_unique_id = f"{route_key}_route_from"
        self._attr_name = "Route from"

    @property
    def native_value(self) -> str | None:
        """Return the route from station."""
        return self._route.get(CONF_FROM)


class NSRouteToSensor(NSAttributeSensorBase):
    """Sensor for route to station."""

    _attr_translation_key = "route_to"

    def __init__(self, coordinator, entry, route, route_key) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, route, route_key)
        self._attr_unique_id = f"{route_key}_route_to"
        self._attr_name = "Route to"

    @property
    def native_value(self) -> str | None:
        """Return the route to station."""
        return self._route.get(CONF_TO)


class NSRouteViaSensor(NSAttributeSensorBase):
    """Sensor for route via station."""

    _attr_translation_key = "route_via"

    def __init__(self, coordinator, entry, route, route_key) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, route, route_key)
        self._attr_unique_id = f"{route_key}_route_via"
        self._attr_name = "Route via"

    @property
    def native_value(self) -> str | None:
        """Return the route via station."""
        return self._route.get(CONF_VIA)
