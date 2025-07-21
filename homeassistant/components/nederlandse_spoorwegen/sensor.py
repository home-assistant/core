"""Support for Nederlandse Spoorwegen public transport."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NSConfigEntry
from .api import get_ns_api_version
from .const import CONF_FROM, CONF_TO, CONF_VIA, DOMAIN
from .coordinator import NSDataUpdateCoordinator
from .ns_logging import UnavailabilityLogger
from .utils import format_time, get_trip_attribute

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class NSSensorEntityDescription(SensorEntityDescription):
    """Describes Nederlandse Spoorwegen sensor entity."""

    value_fn: Callable[[Any, dict[str, Any]], Any] | None = None


SENSOR_DESCRIPTIONS: tuple[NSSensorEntityDescription, ...] = (
    NSSensorEntityDescription(
        key="departure_platform_planned",
        translation_key="departure_platform_planned",
        name="Departure platform planned",
        value_fn=lambda first_trip, route: get_trip_attribute(
            first_trip, "departure_platform_planned"
        ),
    ),
    NSSensorEntityDescription(
        key="departure_platform_actual",
        translation_key="departure_platform_actual",
        name="Departure platform actual",
        value_fn=lambda first_trip, route: get_trip_attribute(
            first_trip, "departure_platform_actual"
        ),
    ),
    NSSensorEntityDescription(
        key="arrival_platform_planned",
        translation_key="arrival_platform_planned",
        name="Arrival platform planned",
        value_fn=lambda first_trip, route: get_trip_attribute(
            first_trip, "arrival_platform_planned"
        ),
    ),
    NSSensorEntityDescription(
        key="arrival_platform_actual",
        translation_key="arrival_platform_actual",
        name="Arrival platform actual",
        value_fn=lambda first_trip, route: get_trip_attribute(
            first_trip, "arrival_platform_actual"
        ),
    ),
    NSSensorEntityDescription(
        key="departure_time_planned",
        translation_key="departure_time_planned",
        name="Departure time planned",
        value_fn=lambda first_trip, route: format_time(
            get_trip_attribute(first_trip, "departure_time_planned")
        ),
    ),
    NSSensorEntityDescription(
        key="departure_time_actual",
        translation_key="departure_time_actual",
        name="Departure time actual",
        value_fn=lambda first_trip, route: format_time(
            get_trip_attribute(first_trip, "departure_time_actual")
        ),
    ),
    NSSensorEntityDescription(
        key="arrival_time_planned",
        translation_key="arrival_time_planned",
        name="Arrival time planned",
        value_fn=lambda first_trip, route: format_time(
            get_trip_attribute(first_trip, "arrival_time_planned")
        ),
    ),
    NSSensorEntityDescription(
        key="arrival_time_actual",
        translation_key="arrival_time_actual",
        name="Arrival time actual",
        value_fn=lambda first_trip, route: format_time(
            get_trip_attribute(first_trip, "arrival_time_actual")
        ),
    ),
    NSSensorEntityDescription(
        key="status",
        translation_key="status",
        name="Status",
        value_fn=lambda first_trip, route: get_trip_attribute(first_trip, "status"),
    ),
    NSSensorEntityDescription(
        key="transfers",
        translation_key="transfers",
        name="Transfers",
        value_fn=lambda first_trip, route: get_trip_attribute(
            first_trip, "nr_transfers"
        ),
    ),
    # Route info sensors
    NSSensorEntityDescription(
        key="route_from",
        translation_key="route_from",
        name="Route from",
        value_fn=lambda first_trip, route: route.get(CONF_FROM),
    ),
    NSSensorEntityDescription(
        key="route_to",
        translation_key="route_to",
        name="Route to",
        value_fn=lambda first_trip, route: route.get(CONF_TO),
    ),
    NSSensorEntityDescription(
        key="route_via",
        translation_key="route_via",
        name="Route via",
        value_fn=lambda first_trip, route: route.get(CONF_VIA),
    ),
)

NEXT_DEPARTURE_DESCRIPTION = NSSensorEntityDescription(
    key="next_departure",
    translation_key="next_departure",
    name="Next departure",
    value_fn=lambda next_trip, route: format_time(
        get_trip_attribute(next_trip, "departure_time_actual")
        or get_trip_attribute(next_trip, "departure_time_planned")
    ),
)


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

    for subentry_id, subentry in entry.subentries.items():
        subentry_entities: list[SensorEntity] = []
        subentry_data = subentry.data

        route = {
            CONF_NAME: subentry_data.get(CONF_NAME, subentry.title),
            CONF_FROM: subentry_data[CONF_FROM],
            CONF_TO: subentry_data[CONF_TO],
            CONF_VIA: subentry_data.get(CONF_VIA),
            "route_id": subentry_id,
        }

        subentry_entities.extend(
            [
                NSSensor(coordinator, entry, route, subentry_id, description)
                for description in SENSOR_DESCRIPTIONS
            ]
        )

        subentry_entities.append(
            NSNextDepartureSensor(
                coordinator, entry, route, subentry_id, NEXT_DEPARTURE_DESCRIPTION
            )
        )

        async_add_entities(subentry_entities, config_subentry_id=subentry_id)


class NSSensor(CoordinatorEntity[NSDataUpdateCoordinator], SensorEntity):
    """Generic NS sensor based on entity description."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by NS"
    entity_description: NSSensorEntityDescription

    def __init__(
        self,
        coordinator: NSDataUpdateCoordinator,
        entry: NSConfigEntry,
        route: dict[str, Any],
        route_key: str,
        description: NSSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._route = route
        self._route_key = route_key

        self._unavailability_logger = UnavailabilityLogger(
            _LOGGER, f"Sensor {route_key}_{description.key}"
        )

        self._attr_unique_id = f"{route_key}_{description.key}"

        if route.get("route_id") and route["route_id"] in entry.subentries:
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
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, entry.entry_id)},
            )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        is_available = (
            super().available
            and self.coordinator.data is not None
            and self._route_key in self.coordinator.data.get("routes", {})
        )

        if not is_available:
            self._unavailability_logger.log_unavailable()
        else:
            self._unavailability_logger.log_recovery()

        return is_available

    @property
    def native_value(self) -> str | int | None:
        """Return the native value of the sensor with robust error handling."""
        if not self.coordinator.data or not self.entity_description.value_fn:
            return None

        try:
            route_data = self.coordinator.data.get("routes", {})
            if not isinstance(route_data, dict):
                _LOGGER.warning("Invalid routes data structure: %s", type(route_data))
                return None

            route_specific_data = route_data.get(self._route_key, {})
            if not isinstance(route_specific_data, dict):
                _LOGGER.debug("No data for route %s", self._route_key)
                return None

            first_trip = route_specific_data.get("first_trip")

            return self.entity_description.value_fn(first_trip, self._route)
        except (TypeError, AttributeError, KeyError) as ex:
            _LOGGER.debug(
                "Failed to get native value for %s: %s", self.entity_description.key, ex
            )
            return None


class NSNextDepartureSensor(NSSensor):
    """Special sensor for next departure that uses next_trip instead of first_trip."""

    @property
    def native_value(self) -> str | None:
        """Return the native value of the sensor with robust error handling."""
        if not self.coordinator.data or not self.entity_description.value_fn:
            return None

        try:
            route_data = self.coordinator.data.get("routes", {})
            if not isinstance(route_data, dict):
                _LOGGER.warning("Invalid routes data structure: %s", type(route_data))
                return None

            route_specific_data = route_data.get(self._route_key, {})
            if not isinstance(route_specific_data, dict):
                _LOGGER.debug("No data for route %s", self._route_key)
                return None

            next_trip = route_specific_data.get("next_trip")

            return self.entity_description.value_fn(next_trip, self._route)
        except (TypeError, AttributeError, KeyError) as ex:
            _LOGGER.debug("Failed to get next departure value: %s", ex)
            return None
