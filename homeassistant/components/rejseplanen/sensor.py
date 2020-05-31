"""
Support for Rejseplanen information from rejseplanen.dk.

For more info on the API see:
https://help.rejseplanen.dk/hc/en-us/articles/214174465-Rejseplanen-s-API
"""
from datetime import datetime, timedelta
import logging
from operator import itemgetter

import rjpl
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, TIME_MINUTES
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_STOP_ID = "stop_id"
ATTR_STOP_NAME = "stop"
ATTR_ROUTE = "route"
ATTR_TYPE = "type"
ATTR_DIRECTION = "direction"
ATTR_DUE_IN = "due_in"
ATTR_DUE_AT = "due_at"
ATTR_NEXT_UP = "next_departures"

ATTRIBUTION = "Data provided by rejseplanen.dk"

CONF_STOP_ID = "stop_id"
CONF_ROUTE = "route"
CONF_DIRECTION = "direction"
CONF_DEPARTURE_TYPE = "departure_type"

DEFAULT_NAME = "Next departure"
ICON = "mdi:bus"

SCAN_INTERVAL = timedelta(minutes=1)

BUS_TYPES = ["BUS", "EXB", "TB"]
TRAIN_TYPES = ["LET", "S", "REG", "IC", "LYN", "TOG"]
METRO_TYPES = ["M"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_ROUTE, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_DIRECTION, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_DEPARTURE_TYPE, default=[]): vol.All(
            cv.ensure_list, [vol.In([*BUS_TYPES, *TRAIN_TYPES, *METRO_TYPES])]
        ),
    }
)


def due_in_minutes(timestamp):
    """Get the time in minutes from a timestamp.

    The timestamp should be in the format day.month.year hour:minute
    """
    diff = datetime.strptime(timestamp, "%d.%m.%y %H:%M") - dt_util.now().replace(
        tzinfo=None
    )

    return int(diff.total_seconds() // 60)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Rejseplanen transport sensor."""
    name = config[CONF_NAME]
    stop_id = config[CONF_STOP_ID]
    route = config.get(CONF_ROUTE)
    direction = config[CONF_DIRECTION]
    departure_type = config[CONF_DEPARTURE_TYPE]

    data = PublicTransportData(stop_id, route, direction, departure_type)
    add_devices(
        [RejseplanenTransportSensor(data, stop_id, route, direction, name)], True
    )


class RejseplanenTransportSensor(Entity):
    """Implementation of Rejseplanen transport sensor."""

    def __init__(self, data, stop_id, route, direction, name):
        """Initialize the sensor."""
        self.data = data
        self._name = name
        self._stop_id = stop_id
        self._route = route
        self._direction = direction
        self._times = self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if not self._times:
            return {ATTR_STOP_ID: self._stop_id, ATTR_ATTRIBUTION: ATTRIBUTION}

        next_up = []
        if len(self._times) > 1:
            next_up = self._times[1:]

        return {
            ATTR_DUE_IN: self._times[0][ATTR_DUE_IN],
            ATTR_DUE_AT: self._times[0][ATTR_DUE_AT],
            ATTR_TYPE: self._times[0][ATTR_TYPE],
            ATTR_ROUTE: self._times[0][ATTR_ROUTE],
            ATTR_DIRECTION: self._times[0][ATTR_DIRECTION],
            ATTR_STOP_NAME: self._times[0][ATTR_STOP_NAME],
            ATTR_STOP_ID: self._stop_id,
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_NEXT_UP: next_up,
        }

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return TIME_MINUTES

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data from rejseplanen.dk and update the states."""
        self.data.update()
        self._times = self.data.info

        if not self._times:
            self._state = None
        else:
            try:
                self._state = self._times[0][ATTR_DUE_IN]
            except TypeError:
                pass


class PublicTransportData:
    """The Class for handling the data retrieval."""

    def __init__(self, stop_id, route, direction, departure_type):
        """Initialize the data object."""
        self.stop_id = stop_id
        self.route = route
        self.direction = direction
        self.departure_type = departure_type
        self.info = []

    def update(self):
        """Get the latest data from rejseplanen."""
        self.info = []

        def intersection(lst1, lst2):
            """Return items contained in both lists."""
            return list(set(lst1) & set(lst2))

        # Limit search to selected types, to get more results
        all_types = not bool(self.departure_type)
        use_train = all_types or bool(intersection(TRAIN_TYPES, self.departure_type))
        use_bus = all_types or bool(intersection(BUS_TYPES, self.departure_type))
        use_metro = all_types or bool(intersection(METRO_TYPES, self.departure_type))

        try:
            results = rjpl.departureBoard(
                int(self.stop_id),
                timeout=5,
                useTrain=use_train,
                useBus=use_bus,
                useMetro=use_metro,
            )
        except rjpl.rjplAPIError as error:
            _LOGGER.debug("API returned error: %s", error)
            return
        except (rjpl.rjplConnectionError, rjpl.rjplHTTPError):
            _LOGGER.debug("Error occurred while connecting to the API")
            return

        # Filter result
        results = [d for d in results if "cancelled" not in d]
        if self.route:
            results = [d for d in results if d["name"] in self.route]
        if self.direction:
            results = [d for d in results if d["direction"] in self.direction]
        if self.departure_type:
            results = [d for d in results if d["type"] in self.departure_type]

        for item in results:
            route = item.get("name")

            due_at_date = item.get("rtDate")
            due_at_time = item.get("rtTime")

            if due_at_date is None:
                due_at_date = item.get("date")  # Scheduled date
            if due_at_time is None:
                due_at_time = item.get("time")  # Scheduled time

            if (
                due_at_date is not None
                and due_at_time is not None
                and route is not None
            ):
                due_at = f"{due_at_date} {due_at_time}"

                departure_data = {
                    ATTR_DUE_IN: due_in_minutes(due_at),
                    ATTR_DUE_AT: due_at,
                    ATTR_TYPE: item.get("type"),
                    ATTR_ROUTE: route,
                    ATTR_DIRECTION: item.get("direction"),
                    ATTR_STOP_NAME: item.get("stop"),
                }
                self.info.append(departure_data)

        if not self.info:
            _LOGGER.debug("No departures with given parameters")

        # Sort the data by time
        self.info = sorted(self.info, key=itemgetter(ATTR_DUE_IN))
