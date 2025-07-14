"""Support for Nederlandse Spoorwegen public transport."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory  # type: ignore[attr-defined]
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NSConfigEntry
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

    # Always create the service sensor
    entities: list[SensorEntity] = [NSServiceSensor(coordinator, entry)]

    # Create trip sensors for each route
    if coordinator.data and "routes" in coordinator.data:
        for route_key, route_data in coordinator.data["routes"].items():
            route = route_data["route"]
            # Validate route has required fields before creating sensor
            if not all(key in route for key in (CONF_NAME, CONF_FROM, CONF_TO)):
                _LOGGER.warning(
                    "Skipping sensor creation for malformed route: %s", route
                )
                continue
            entities.append(
                NSTripSensor(
                    coordinator,
                    entry,
                    route,
                    route_key,
                )
            )

    async_add_entities(entities)


class NSServiceSensor(CoordinatorEntity[NSDataUpdateCoordinator], SensorEntity):
    """Sensor representing the NS service status."""

    _attr_has_entity_name = True
    _attr_translation_key = "service"
    _attr_attribution = "Data provided by NS"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: NSDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the service sensor."""
        super().__init__(coordinator)
        _LOGGER.debug("Creating NSServiceSensor for entry: %s", config_entry.entry_id)
        self._attr_unique_id = f"{config_entry.entry_id}_service"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="Nederlandse Spoorwegen",
            manufacturer="Nederlandse Spoorwegen",
            model="NS API",
            sw_version="1.0",
            configuration_url="https://www.ns.nl/",
        )

    @property
    def native_value(self) -> str:
        """Return the state of the service."""
        if not self.coordinator.data:
            return "waiting_for_data"
        routes = self.coordinator.data.get("routes", {})
        if not routes:
            return "no_routes"
        has_data = any(route_data.get("trips") for route_data in routes.values())
        return "connected" if has_data else "disconnected"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}
        routes = self.coordinator.data.get("routes", {})
        return {
            "total_routes": len(routes),
            "active_routes": len([r for r in routes.values() if r.get("trips")]),
        }


class NSTripSensor(CoordinatorEntity[NSDataUpdateCoordinator], SensorEntity):
    """Sensor representing a specific NS trip route."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: NSDataUpdateCoordinator,
        entry: ConfigEntry,
        route: dict[str, Any],
        route_key: str,
    ) -> None:
        """Initialize NSTripSensor with coordinator, entry, route, and route_key."""
        super().__init__(coordinator)
        self._route = route
        self._route_key = route_key
        self._entry = entry
        _LOGGER.debug(
            "Creating NSTripSensor: entry_id=%s, route_key=%s",
            entry.entry_id,
            route_key,
        )
        self._attr_name = route[CONF_NAME]
        route_id = route.get("route_id", route_key)
        self._attr_unique_id = f"{entry.entry_id}_{route_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )

    @property
    def native_value(self) -> str | None:
        """Return the next departure time or a better state."""
        if not self.coordinator.data:
            return "waiting_for_data"
        route_data = self.coordinator.data.get("routes", {}).get(self._route_key)
        if not route_data:
            return "route_unavailable"
        first_trip = route_data.get("first_trip")
        if not first_trip:
            return "no_trip"
        departure_time = getattr(first_trip, "departure_time_actual", None) or getattr(
            first_trip, "departure_time_planned", None
        )
        if departure_time and isinstance(departure_time, datetime):
            return departure_time.strftime("%H:%M")
        return "no_time"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._route_key in self.coordinator.data.get("routes", {})
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}
        route_data = self.coordinator.data.get("routes", {}).get(self._route_key, {})
        first_trip = route_data.get("first_trip")
        next_trip = route_data.get("next_trip")
        attributes = {
            "route_from": self._route.get(CONF_FROM),
            "route_to": self._route.get(CONF_TO),
            "route_via": self._route.get(CONF_VIA),
        }
        if first_trip:
            attributes.update(
                {
                    "departure_platform_planned": getattr(
                        first_trip, "departure_platform_planned", None
                    ),
                    "departure_platform_actual": getattr(
                        first_trip, "departure_platform_actual", None
                    ),
                    "arrival_platform_planned": getattr(
                        first_trip, "arrival_platform_planned", None
                    ),
                    "arrival_platform_actual": getattr(
                        first_trip, "arrival_platform_actual", None
                    ),
                    "status": getattr(first_trip, "status", None),
                    "nr_transfers": getattr(first_trip, "nr_transfers", None),
                }
            )
            departure_planned = getattr(first_trip, "departure_time_planned", None)
            departure_actual = getattr(first_trip, "departure_time_actual", None)
            arrival_planned = getattr(first_trip, "arrival_time_planned", None)
            arrival_actual = getattr(first_trip, "arrival_time_actual", None)
            if departure_planned:
                attributes["departure_time_planned"] = departure_planned.strftime(
                    "%H:%M"
                )
            if departure_actual:
                attributes["departure_time_actual"] = departure_actual.strftime("%H:%M")
            if arrival_planned:
                attributes["arrival_time_planned"] = arrival_planned.strftime("%H:%M")
            if arrival_actual:
                attributes["arrival_time_actual"] = arrival_actual.strftime("%H:%M")
        if next_trip:
            next_departure = getattr(
                next_trip, "departure_time_actual", None
            ) or getattr(next_trip, "departure_time_planned", None)
            if next_departure:
                attributes["next_departure"] = next_departure.strftime("%H:%M")
        return attributes
