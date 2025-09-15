"""Support for Nederlandse Spoorwegen public transport."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle, dt as dt_util
from homeassistant.util.dt import parse_time

from . import NSConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_ROUTES = "routes"
CONF_FROM = "from"
CONF_TO = "to"
CONF_VIA = "via"
CONF_TIME = "time"


MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

ROUTE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_FROM): cv.string,
        vol.Required(CONF_TO): cv.string,
        vol.Optional(CONF_VIA): cv.string,
        vol.Optional(CONF_TIME): cv.time,
    }
)

ROUTES_SCHEMA = vol.All(cv.ensure_list, [ROUTE_SCHEMA])

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_API_KEY): cv.string, vol.Optional(CONF_ROUTES): ROUTES_SCHEMA}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the departure sensor."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )
    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            breaks_in_ha_version="2026.4.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result.get('reason')}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Nederlandse Spoorwegen",
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2026.4.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Nederlandse Spoorwegen",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the departure sensor from a config entry."""

    client = config_entry.runtime_data

    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "route":
            continue

        async_add_entities(
            [
                NSDepartureSensor(
                    client,
                    subentry.data[CONF_NAME],
                    subentry.data[CONF_FROM],
                    subentry.data[CONF_TO],
                    subentry.data.get(CONF_VIA),
                    parse_time(subentry.data[CONF_TIME])
                    if CONF_TIME in subentry.data
                    else None,
                )
            ],
            config_subentry_id=subentry.subentry_id,
            update_before_add=True,
        )


class NSDepartureSensor(SensorEntity):
    """Implementation of a NS Departure Sensor."""

    _attr_attribution = "Data provided by NS"
    _attr_icon = "mdi:train"

    def __init__(self, nsapi, name, departure, heading, via, time):
        """Initialize the sensor."""
        self._nsapi = nsapi
        self._name = name
        self._departure = departure
        self._via = via
        self._heading = heading
        self._time = time
        self._state = None
        self._trips = None
        self._first_trip = None
        self._next_trip = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the next departure time."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if not self._trips or self._first_trip is None:
            return None

        # Initialize route with departure, extend with trip parts if they exist
        route = [self._first_trip.departure]
        if self._first_trip.trip_parts:
            route.extend(k.destination for k in self._first_trip.trip_parts)

        # Static attributes
        attributes = {
            "going": self._first_trip.going,
            "departure_time_planned": None,
            "departure_time_actual": None,
            "departure_delay": False,
            "departure_platform_planned": self._first_trip.departure_platform_planned,
            "departure_platform_actual": self._first_trip.departure_platform_actual,
            "arrival_time_planned": None,
            "arrival_time_actual": None,
            "arrival_delay": False,
            "arrival_platform_planned": self._first_trip.arrival_platform_planned,
            "arrival_platform_actual": self._first_trip.arrival_platform_actual,
            "next": None,
            "status": self._first_trip.status.lower(),
            "transfers": self._first_trip.nr_transfers,
            "route": route,
            "remarks": None,
        }

        # Planned departure attributes
        if self._first_trip.departure_time_planned is not None:
            attributes["departure_time_planned"] = (
                self._first_trip.departure_time_planned.strftime("%H:%M")
            )

        # Actual departure attributes
        if self._first_trip.departure_time_actual is not None:
            attributes["departure_time_actual"] = (
                self._first_trip.departure_time_actual.strftime("%H:%M")
            )

        # Delay departure attributes
        if (
            attributes["departure_time_planned"]
            and attributes["departure_time_actual"]
            and attributes["departure_time_planned"]
            != attributes["departure_time_actual"]
        ):
            attributes["departure_delay"] = True

        # Planned arrival attributes
        if self._first_trip.arrival_time_planned is not None:
            attributes["arrival_time_planned"] = (
                self._first_trip.arrival_time_planned.strftime("%H:%M")
            )

        # Actual arrival attributes
        if self._first_trip.arrival_time_actual is not None:
            attributes["arrival_time_actual"] = (
                self._first_trip.arrival_time_actual.strftime("%H:%M")
            )

        # Delay arrival attributes
        if (
            attributes["arrival_time_planned"]
            and attributes["arrival_time_actual"]
            and attributes["arrival_time_planned"] != attributes["arrival_time_actual"]
        ):
            attributes["arrival_delay"] = True

        # Next attributes
        if self._next_trip.departure_time_actual is not None:
            attributes["next"] = self._next_trip.departure_time_actual.strftime("%H:%M")
        elif self._next_trip.departure_time_planned is not None:
            attributes["next"] = self._next_trip.departure_time_planned.strftime(
                "%H:%M"
            )
        else:
            attributes["next"] = None

        return attributes

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Get the trip information."""

        # If looking for a specific trip time, update around that trip time only.
        if self._time and (
            (datetime.now() + timedelta(minutes=30)).time() < self._time
            or (datetime.now() - timedelta(minutes=30)).time() > self._time
        ):
            self._state = None
            self._trips = None
            self._first_trip = None
            return

        # Set the search parameter to search from a specific trip time
        # or to just search for next trip.
        if self._time:
            trip_time = (
                datetime.today()
                .replace(hour=self._time.hour, minute=self._time.minute)
                .strftime("%d-%m-%Y %H:%M")
            )
        else:
            trip_time = dt_util.now().strftime("%d-%m-%Y %H:%M")

        try:
            self._trips = self._nsapi.get_trips(
                trip_time, self._departure, self._via, self._heading, True, 0, 2
            )
            if self._trips:
                all_times = []

                # If a train is delayed we can observe this through departure_time_actual.
                for trip in self._trips:
                    if trip.departure_time_actual is None:
                        all_times.append(trip.departure_time_planned)
                    else:
                        all_times.append(trip.departure_time_actual)

                # Remove all trains that already left.
                filtered_times = [
                    (i, time)
                    for i, time in enumerate(all_times)
                    if time > dt_util.now()
                ]

                if len(filtered_times) > 0:
                    sorted_times = sorted(filtered_times, key=lambda x: x[1])
                    self._first_trip = self._trips[sorted_times[0][0]]
                    self._state = sorted_times[0][1].strftime("%H:%M")

                    # Filter again to remove trains that leave at the exact same time.
                    filtered_times = [
                        (i, time)
                        for i, time in enumerate(all_times)
                        if time > sorted_times[0][1]
                    ]

                    if len(filtered_times) > 0:
                        sorted_times = sorted(filtered_times, key=lambda x: x[1])
                        self._next_trip = self._trips[sorted_times[0][0]]
                    else:
                        self._next_trip = None

                else:
                    self._first_trip = None
                    self._state = None

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ) as error:
            _LOGGER.error("Couldn't fetch trip info: %s", error)
