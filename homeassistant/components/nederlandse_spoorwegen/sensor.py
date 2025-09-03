"""Support for Nederlandse Spoorwegen public transport."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NSConfigEntry
from .const import CONF_FROM, CONF_ROUTES, CONF_TIME, CONF_TO, CONF_VIA, DOMAIN
from .coordinator import NSDataUpdateCoordinator
from .ns_logging import UnavailabilityLogger
from .utils import format_time, get_trip_attribute

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to prevent overwhelming the NS API
PARALLEL_UPDATES = 0  # 0 = unlimited, since we use coordinator pattern

# Schema for a single route in YAML
ROUTE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_FROM): cv.string,
        vol.Required(CONF_TO): cv.string,
        vol.Optional(CONF_VIA): cv.string,
        vol.Optional(CONF_TIME): cv.string,
    }
)

# Platform schema for sensor YAML configuration
PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_ROUTES, default=[]): vol.All(cv.ensure_list, [ROUTE_SCHEMA]),
    }
)


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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up NS sensors from YAML sensor platform configuration.

    This function handles the legacy YAML sensor platform configuration format:
    sensor:
      - platform: nederlandse_spoorwegen
        api_key: ...
        routes: ...

    It creates an import flow to migrate the configuration to the new config entry format,
    which provides a better user experience with the UI and subentries for routes.
    """
    _LOGGER.warning(
        "YAML sensor platform configuration for Nederlandse Spoorwegen is deprecated. "
        "Your configuration is being imported to the UI. "
        "Please remove the sensor platform configuration from YAML after import is complete"
    )

    # Create import flow for sensor platform configuration
    # The config flow will handle validation and integration setup
    if config:
        _LOGGER.debug("Importing sensor platform YAML configuration: %s", config)
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "import"},
                data=config,  # Pass the sensor platform config to the flow
            )
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NS sensors from a config entry.

    This function handles the modern config entry-based setup where:
    - The integration is configured via UI or imported from YAML
    - Routes are stored as subentries for better management
    - Each route gets its own device in the device registry
    - Sensors are created based on the coordinator data

    This is the preferred setup method as it provides:
    - Better UI/UX with proper config flows
    - Individual route management via subentries
    - Proper device registry integration
    - Easier maintenance and debugging
    """
    coordinator = entry.runtime_data.coordinator
    if coordinator is None:
        _LOGGER.error("Coordinator not found in runtime_data for NS integration")
        return

    for subentry_id, subentry in entry.subentries.items():
        subentry_data = subentry.data

        route = {
            CONF_NAME: subentry_data.get(CONF_NAME, subentry.title),
            CONF_FROM: subentry_data[CONF_FROM],
            CONF_TO: subentry_data[CONF_TO],
            CONF_VIA: subentry_data.get(CONF_VIA),
            "route_id": subentry_id,
        }

        # Create one NSDepartureSensor per subentry (instead of multiple sensors)
        departure_sensor = NSDepartureSensor(coordinator, entry, route, subentry_id)
        async_add_entities([departure_sensor], config_subentry_id=subentry_id)


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
                sw_version="1.0.0",
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


class NSDepartureSensor(NSSensor):
    """Implementation of a NS Departure Sensor."""

    _attr_has_entity_name = True
    _attr_attribution = "Data provided by NS"
    _attr_icon = "mdi:train"

    def __init__(
        self,
        coordinator: NSDataUpdateCoordinator,
        entry: NSConfigEntry,
        route: dict[str, Any],
        route_key: str,
    ) -> None:
        """Initialize the sensor."""
        # Create a custom entity description for departure sensor
        description = NSSensorEntityDescription(
            key="departure",
            translation_key="departure",
            name=route.get(
                CONF_NAME, f"{route.get(CONF_FROM)} to {route.get(CONF_TO)}"
            ),
            value_fn=lambda first_trip, route: format_time(
                get_trip_attribute(first_trip, "departure_time_actual")
                or get_trip_attribute(first_trip, "departure_time_planned")
            ),
        )

        super().__init__(coordinator, entry, route, route_key, description)

        # Override unique_id to maintain compatibility
        self._attr_unique_id = f"{route_key}_departure"

        # Store additional route information for legacy compatibility
        self._departure = route.get(CONF_FROM)
        self._via = route.get(CONF_VIA)
        self._heading = route.get(CONF_TO)
        self._time = route.get(CONF_TIME)
        self._state: str | int | None = None
        self._trips = None
        self._first_trip = None
        self._next_trip = None

    @property
    def native_value(self) -> str | None:
        """Return the next departure time."""
        # Use parent's logic to get the departure time
        departure_time = super().native_value

        # Update internal state for extra_state_attributes compatibility
        self._state = departure_time

        # Update internal trip data for legacy attributes
        if self.coordinator.data:
            route_data = self.coordinator.data.get("routes", {})
            if isinstance(route_data, dict):
                route_specific_data = route_data.get(self._route_key, {})
                if isinstance(route_specific_data, dict):
                    self._trips = route_specific_data.get("trips", [])
                    self._first_trip = route_specific_data.get("first_trip")
                    self._next_trip = route_specific_data.get("next_trip")

        return departure_time if isinstance(departure_time, str) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if not self._trips or self._first_trip is None:
            return None

        route = []
        trip_parts = get_trip_attribute(self._first_trip, "trip_parts")
        if trip_parts:
            departure = get_trip_attribute(self._first_trip, "departure")
            if departure:
                route = [departure]
                route.extend(
                    get_trip_attribute(part, "destination") or "" for part in trip_parts
                )

        # Static attributes
        attributes = {
            "going": get_trip_attribute(self._first_trip, "going"),
            "departure_time_planned": None,
            "departure_time_actual": None,
            "departure_delay": False,
            "departure_platform_planned": get_trip_attribute(
                self._first_trip, "departure_platform_planned"
            ),
            "departure_platform_actual": get_trip_attribute(
                self._first_trip, "departure_platform_actual"
            ),
            "arrival_time_planned": None,
            "arrival_time_actual": None,
            "arrival_delay": False,
            "arrival_platform_planned": get_trip_attribute(
                self._first_trip, "arrival_platform_planned"
            ),
            "arrival_platform_actual": get_trip_attribute(
                self._first_trip, "arrival_platform_actual"
            ),
            "next": None,
            "status": (get_trip_attribute(self._first_trip, "status") or "").lower(),
            "transfers": get_trip_attribute(self._first_trip, "nr_transfers"),
            "route": route,
            "remarks": None,
        }

        # Planned departure attributes
        departure_time_planned = get_trip_attribute(
            self._first_trip, "departure_time_planned"
        )
        if departure_time_planned is not None:
            attributes["departure_time_planned"] = format_time(departure_time_planned)

        # Actual departure attributes
        departure_time_actual = get_trip_attribute(
            self._first_trip, "departure_time_actual"
        )
        if departure_time_actual is not None:
            attributes["departure_time_actual"] = format_time(departure_time_actual)

        # Delay departure attributes
        if (
            attributes["departure_time_planned"]
            and attributes["departure_time_actual"]
            and attributes["departure_time_planned"]
            != attributes["departure_time_actual"]
        ):
            attributes["departure_delay"] = True

        # Planned arrival attributes
        arrival_time_planned = get_trip_attribute(
            self._first_trip, "arrival_time_planned"
        )
        if arrival_time_planned is not None:
            attributes["arrival_time_planned"] = format_time(arrival_time_planned)

        # Actual arrival attributes
        arrival_time_actual = get_trip_attribute(
            self._first_trip, "arrival_time_actual"
        )
        if arrival_time_actual is not None:
            attributes["arrival_time_actual"] = format_time(arrival_time_actual)

        # Delay arrival attributes
        if (
            attributes["arrival_time_planned"]
            and attributes["arrival_time_actual"]
            and attributes["arrival_time_planned"] != attributes["arrival_time_actual"]
        ):
            attributes["arrival_delay"] = True

        # Next attributes
        if self._next_trip:
            next_departure_actual = get_trip_attribute(
                self._next_trip, "departure_time_actual"
            )
            next_departure_planned = get_trip_attribute(
                self._next_trip, "departure_time_planned"
            )

            if next_departure_actual is not None:
                attributes["next"] = format_time(next_departure_actual)
            elif next_departure_planned is not None:
                attributes["next"] = format_time(next_departure_planned)
            else:
                attributes["next"] = None

        return attributes
