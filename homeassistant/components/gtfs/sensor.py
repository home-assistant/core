"""Support for GTFS."""
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_ARRIVAL,
    ATTR_BICYCLE,
    ATTR_DAY,
    ATTR_DROP_OFF_DESTINATION,
    ATTR_DROP_OFF_ORIGIN,
    ATTR_FIRST,
    ATTR_INFO,
    ATTR_LAST,
    ATTR_LOCATION_DESTINATION,
    ATTR_LOCATION_ORIGIN,
    ATTR_OFFSET,
    ATTR_PICKUP_DESTINATION,
    ATTR_PICKUP_ORIGIN,
    ATTR_ROUTE_TYPE,
    ATTR_TIMEPOINT_DESTINATION,
    ATTR_TIMEPOINT_ORIGIN,
    ATTR_WHEELCHAIR,
    ATTR_WHEELCHAIR_DESTINATION,
    ATTR_WHEELCHAIR_ORIGIN,
    BICYCLE_ALLOWED_DEFAULT,
    BICYCLE_ALLOWED_OPTIONS,
    DEFAULT_NAME,
    DOMAIN,
    DROP_OFF_TYPE_DEFAULT,
    DROP_OFF_TYPE_OPTIONS,
    ICON,
    ICONS,
    LOCATION_TYPE_DEFAULT,
    LOCATION_TYPE_OPTIONS,
    PICKUP_TYPE_DEFAULT,
    PICKUP_TYPE_OPTIONS,
    ROUTE_TYPE_OPTIONS,
    TIMEPOINT_DEFAULT,
    TIMEPOINT_OPTIONS,
    WHEELCHAIR_ACCESS_DEFAULT,
    WHEELCHAIR_ACCESS_OPTIONS,
    WHEELCHAIR_BOARDING_DEFAULT,
    WHEELCHAIR_BOARDING_OPTIONS,
)
from .coordinator import GTFSUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize the setup."""
    coordinator: GTFSUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        "coordinator"
    ]

    await coordinator.async_config_entry_first_refresh()

    sensors = [
        GTFSDepartureSensor(coordinator),
    ]

    async_add_entities(sensors, False)


class GTFSDepartureSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a GTFS departure sensor."""

    def __init__(self, coordinator) -> None:
        """Initialize the GTFSsensor."""
        super().__init__(coordinator)

        self._name = coordinator.data["name"]
        self._attributes: dict[str, Any] = {}

        self._attr_unique_id = f"gtfs-{self._name}"
        self._attr_device_info = DeviceInfo(
            name=f"GTFS - {self._name}",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"GTFS - {self._name}")},
            manufacturer="GTFS",
            model=self._name,
        )
        self._attributes = self._update_attrs()
        self._attr_extra_state_attributes = self._attributes

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        super()._handle_coordinator_update()

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return self._icon

    #    @property
    def _update_attrs(self):  # noqa: C901 PLR0911
        self._pygtfs = self.coordinator.data["schedule"]
        self.origin = self.coordinator.data["origin"]
        self.destination = self.coordinator.data["destination"]
        self._include_tomorrow = self.coordinator.data["include_tomorrow"]
        self._offset = self.coordinator.data["offset"]
        self._departure = self.coordinator.data["next_departure"]
        self._available = False
        self._icon = ICON
        self._state: datetime.datetime | None = None
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._origin = None
        self._destination = None
        self._trip = None
        self._route = None
        self._agency = None
        # Fetch valid stop information once
        if not self._origin:
            stops = self._pygtfs.stops_by_id(self.origin)
            if not stops:
                self._available = False
                _LOGGER.warning("Origin stop ID %s not found", self.origin)
                return
            self._origin = stops[0]

        if not self._destination:
            stops = self._pygtfs.stops_by_id(self.destination)
            if not stops:
                self._available = False
                _LOGGER.warning("Destination stop ID %s not found", self.destination)
                return
            self._destination = stops[0]

        # Fetch trip and route details once, unless updated
        if not self._departure:
            self._trip = None
        else:
            trip_id = self._departure["trip_id"]
            if not self._trip or self._trip.trip_id != trip_id:
                _LOGGER.debug("Fetching trip details for %s", trip_id)
                self._trip = self._pygtfs.trips_by_id(trip_id)[0]

            route_id = self._departure["route_id"]
            if not self._route or self._route.route_id != route_id:
                _LOGGER.debug("Fetching route details for %s", route_id)
                self._route = self._pygtfs.routes_by_id(route_id)[0]

        # fetch next departures
        self._departure = self.coordinator.data["next_departure"]
        if not self._departure:
            self._next_departures = None
        else:
            self._next_departures = self._departure["next_departures"]

        # Fetch agency details exactly once
        if self._agency is None and self._route:
            _LOGGER.debug("Fetching agency details for %s", self._route.agency_id)
            try:
                self._agency = self._pygtfs.agencies_by_id(self._route.agency_id)[0]
            except IndexError:
                _LOGGER.warning(
                    (
                        "Agency ID '%s' was not found in agency table, "
                        "you may want to update the routes database table "
                        "to fix this missing reference"
                    ),
                    self._route.agency_id,
                )
                self._agency = False

        # Define the state as a UTC timestamp with ISO 8601 format
        if not self._departure:
            self._state = None
        elif self._agency:
            _LOGGER.debug(
                "Self._departure time for state value TZ: %s ",
                {self._departure["departure_time"]},
            )
            self._state = self._departure["departure_time"].replace(
                tzinfo=dt_util.get_time_zone(self._agency.agency_timezone)
            )
        else:
            _LOGGER.debug(
                "Self._departure time for state value UTC: %s",
                {self._departure["departure_time"]},
            )
            self._state = self._departure["departure_time"].replace(tzinfo=dt_util.UTC)
        # settin state value
        self._attr_native_value = self._state

        if self._agency:
            self._attr_attribution = self._agency.agency_name
        else:
            self._attr_attribution = None

        if self._route:
            self._icon = ICONS.get(self._route.route_type, ICON)
        else:
            self._icon = ICON

        name = (
            f"{getattr(self._agency, 'agency_name', DEFAULT_NAME)} "
            f"{self.origin} to {self.destination} next departure"
        )
        if not self._departure:
            name = f"{DEFAULT_NAME}"
        self._name = self._name or name

        # Add departure information
        if self._departure:
            self._attributes[ATTR_ARRIVAL] = dt_util.as_utc(
                self._departure["arrival_time"]
            ).isoformat()

            self._attributes[ATTR_DAY] = self._departure["day"]

            if self._departure[ATTR_FIRST] is not None:
                self._attributes[ATTR_FIRST] = self._departure["first"]
            elif ATTR_FIRST in self._attributes:
                del self._attributes[ATTR_FIRST]

            if self._departure[ATTR_LAST] is not None:
                self._attributes[ATTR_LAST] = self._departure["last"]
            elif ATTR_LAST in self._attributes:
                del self._attributes[ATTR_LAST]
        else:
            if ATTR_ARRIVAL in self._attributes:
                del self._attributes[ATTR_ARRIVAL]
            if ATTR_DAY in self._attributes:
                del self._attributes[ATTR_DAY]
            if ATTR_FIRST in self._attributes:
                del self._attributes[ATTR_FIRST]
            if ATTR_LAST in self._attributes:
                del self._attributes[ATTR_LAST]

        # Add contextual information
        self._attributes[ATTR_OFFSET] = self._offset

        if self._state is None:
            self._attributes[ATTR_INFO] = (
                "No more departures"
                if self._include_tomorrow
                else "No more departures today"
            )
        elif ATTR_INFO in self._attributes:
            del self._attributes[ATTR_INFO]

        # Add extra metadata
        key = "agency_id"
        if self._agency and key not in self._attributes:
            self.append_keys(self.dict_for_table(self._agency), "Agency")

        key = "origin_station_stop_id"
        if self._origin and key not in self._attributes:
            self.append_keys(self.dict_for_table(self._origin), "Origin Station")
            self._attributes[ATTR_LOCATION_ORIGIN] = LOCATION_TYPE_OPTIONS.get(
                self._origin.location_type, LOCATION_TYPE_DEFAULT
            )
            self._attributes[ATTR_WHEELCHAIR_ORIGIN] = WHEELCHAIR_BOARDING_OPTIONS.get(
                self._origin.wheelchair_boarding, WHEELCHAIR_BOARDING_DEFAULT
            )

        key = "destination_station_stop_id"
        if self._destination and key not in self._attributes:
            self.append_keys(
                self.dict_for_table(self._destination), "Destination Station"
            )
            self._attributes[ATTR_LOCATION_DESTINATION] = LOCATION_TYPE_OPTIONS.get(
                self._destination.location_type, LOCATION_TYPE_DEFAULT
            )
            self._attributes[
                ATTR_WHEELCHAIR_DESTINATION
            ] = WHEELCHAIR_BOARDING_OPTIONS.get(
                self._destination.wheelchair_boarding, WHEELCHAIR_BOARDING_DEFAULT
            )

        # Manage Route metadata
        key = "route_id"
        if not self._route and key in self._attributes:
            self.remove_keys("Route")
        elif self._route and (
            key not in self._attributes or self._attributes[key] != self._route.route_id
        ):
            self.append_keys(self.dict_for_table(self._route), "Route")
            self._attributes[ATTR_ROUTE_TYPE] = ROUTE_TYPE_OPTIONS[
                self._route.route_type
            ]

        # Manage Trip metadata
        key = "trip_id"
        if not self._trip and key in self._attributes:
            self.remove_keys("Trip")
        elif self._trip and (
            key not in self._attributes or self._attributes[key] != self._trip.trip_id
        ):
            self.append_keys(self.dict_for_table(self._trip), "Trip")
            self._attributes[ATTR_BICYCLE] = BICYCLE_ALLOWED_OPTIONS.get(
                self._trip.bikes_allowed, BICYCLE_ALLOWED_DEFAULT
            )
            self._attributes[ATTR_WHEELCHAIR] = WHEELCHAIR_ACCESS_OPTIONS.get(
                self._trip.wheelchair_accessible, WHEELCHAIR_ACCESS_DEFAULT
            )

        # Manage Stop Times metadata
        prefix = "origin_stop"
        if self._departure:
            self.append_keys(self._departure["origin_stop_time"], prefix)
            self._attributes[ATTR_DROP_OFF_ORIGIN] = DROP_OFF_TYPE_OPTIONS.get(
                self._departure["origin_stop_time"]["Drop Off Type"],
                DROP_OFF_TYPE_DEFAULT,
            )
            self._attributes[ATTR_PICKUP_ORIGIN] = PICKUP_TYPE_OPTIONS.get(
                self._departure["origin_stop_time"]["Pickup Type"], PICKUP_TYPE_DEFAULT
            )
            self._attributes[ATTR_TIMEPOINT_ORIGIN] = TIMEPOINT_OPTIONS.get(
                self._departure["origin_stop_time"]["Timepoint"], TIMEPOINT_DEFAULT
            )
        else:
            self.remove_keys(prefix)

        _LOGGER.debug(
            "Destination_stop_time %s", self._departure["destination_stop_time"]
        )
        prefix = "destination_stop"
        if self._departure:
            self.append_keys(self._departure["destination_stop_time"], prefix)
            self._attributes[ATTR_DROP_OFF_DESTINATION] = DROP_OFF_TYPE_OPTIONS.get(
                self._departure["destination_stop_time"]["Drop Off Type"],
                DROP_OFF_TYPE_DEFAULT,
            )
            self._attributes[ATTR_PICKUP_DESTINATION] = PICKUP_TYPE_OPTIONS.get(
                self._departure["destination_stop_time"]["Pickup Type"],
                PICKUP_TYPE_DEFAULT,
            )
            self._attributes[ATTR_TIMEPOINT_DESTINATION] = TIMEPOINT_OPTIONS.get(
                self._departure["destination_stop_time"]["Timepoint"], TIMEPOINT_DEFAULT
            )
        else:
            self.remove_keys(prefix)

        # Add next departures
        prefix = "next_departures"
        self._attributes["next_departures"] = []
        if self._next_departures:
            self._attributes["next_departures"] = self._departure["next_departures"][
                :10
            ]

        self._attributes["updated_at"] = dt_util.now().replace(tzinfo=None)
        self._attr_extra_state_attributes = self._attributes
        return self._attr_extra_state_attributes

    @staticmethod
    def dict_for_table(resource: Any) -> dict:
        """Return a dictionary for the SQLAlchemy resource given."""
        _dict = {}
        for column in resource.__table__.columns:
            _dict[column.name] = str(getattr(resource, column.name))
        return _dict

    def append_keys(self, resource: dict, prefix: str | None = None) -> None:
        """Properly format key val pairs to append to attributes."""
        for attr, val in resource.items():
            if val == "" or val is None or attr == "feed_id":
                continue
            key = attr
            if prefix and not key.startswith(prefix):
                key = f"{prefix} {key}"
            key = slugify(key)
            self._attributes[key] = val

    def remove_keys(self, prefix: str) -> None:
        """Remove attributes whose key starts with prefix."""
        self._attributes = {
            k: v for k, v in self._attributes.items() if not k.startswith(prefix)
        }
