"""Support for GTFS (Google/General Transport Format Schema)."""
import datetime
import logging
import os
import threading
from typing import Any, Callable, Optional

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_NAME, CONF_OFFSET, DEVICE_CLASS_TIMESTAMP,
    STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

ATTR_ARRIVAL = 'arrival'
ATTR_BICYCLE = 'trip_bikes_allowed_state'
ATTR_DAY = 'day'
ATTR_FIRST = 'first'
ATTR_DROP_OFF_DESTINATION = 'destination_stop_drop_off_type_state'
ATTR_DROP_OFF_ORIGIN = 'origin_stop_drop_off_type_state'
ATTR_INFO = 'info'
ATTR_OFFSET = CONF_OFFSET
ATTR_LAST = 'last'
ATTR_LOCATION_DESTINATION = 'destination_station_location_type_name'
ATTR_LOCATION_ORIGIN = 'origin_station_location_type_name'
ATTR_PICKUP_DESTINATION = 'destination_stop_pickup_type_state'
ATTR_PICKUP_ORIGIN = 'origin_stop_pickup_type_state'
ATTR_ROUTE_TYPE = 'route_type_name'
ATTR_TIMEPOINT_DESTINATION = 'destination_stop_timepoint_exact'
ATTR_TIMEPOINT_ORIGIN = 'origin_stop_timepoint_exact'
ATTR_WHEELCHAIR = 'trip_wheelchair_access_available'
ATTR_WHEELCHAIR_DESTINATION = \
    'destination_station_wheelchair_boarding_available'
ATTR_WHEELCHAIR_ORIGIN = 'origin_station_wheelchair_boarding_available'

CONF_DATA = 'data'
CONF_DESTINATION = 'destination'
CONF_ORIGIN = 'origin'
CONF_TOMORROW = 'include_tomorrow'

DEFAULT_NAME = 'GTFS Sensor'
DEFAULT_PATH = 'gtfs'

BICYCLE_ALLOWED_DEFAULT = STATE_UNKNOWN
BICYCLE_ALLOWED_OPTIONS = {
    1: True,
    2: False,
}
DROP_OFF_TYPE_DEFAULT = STATE_UNKNOWN
DROP_OFF_TYPE_OPTIONS = {
    0: 'Regular',
    1: 'Not Available',
    2: 'Call Agency',
    3: 'Contact Driver',
}
ICON = 'mdi:train'
ICONS = {
    0: 'mdi:tram',
    1: 'mdi:subway',
    2: 'mdi:train',
    3: 'mdi:bus',
    4: 'mdi:ferry',
    5: 'mdi:train-variant',
    6: 'mdi:gondola',
    7: 'mdi:stairs',
}
LOCATION_TYPE_DEFAULT = 'Stop'
LOCATION_TYPE_OPTIONS = {
    0: 'Station',
    1: 'Stop',
    2: "Station Entrance/Exit",
    3: 'Other',
}
PICKUP_TYPE_DEFAULT = STATE_UNKNOWN
PICKUP_TYPE_OPTIONS = {
    0: 'Regular',
    1: "None Available",
    2: "Call Agency",
    3: "Contact Driver",
}
ROUTE_TYPE_OPTIONS = {
    0: 'Tram',
    1: 'Subway',
    2: 'Rail',
    3: 'Bus',
    4: 'Ferry',
    5: "Cable Tram",
    6: "Aerial Lift",
    7: 'Funicular',
}
TIMEPOINT_DEFAULT = True
TIMEPOINT_OPTIONS = {
    0: False,
    1: True,
}
WHEELCHAIR_ACCESS_DEFAULT = STATE_UNKNOWN
WHEELCHAIR_ACCESS_OPTIONS = {
    1: True,
    2: False,
}
WHEELCHAIR_BOARDING_DEFAULT = STATE_UNKNOWN
WHEELCHAIR_BOARDING_OPTIONS = {
    1: True,
    2: False,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({  # type: ignore
    vol.Required(CONF_ORIGIN): cv.string,
    vol.Required(CONF_DESTINATION): cv.string,
    vol.Required(CONF_DATA): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_OFFSET, default=0): cv.time_period,
    vol.Optional(CONF_TOMORROW, default=False): cv.boolean,
})


def get_next_departure(schedule: Any, start_station_id: Any,
                       end_station_id: Any, offset: cv.time_period,
                       include_tomorrow: bool = False) -> dict:
    """Get the next departure for the given schedule."""
    now = datetime.datetime.now() + offset
    now_date = now.strftime(dt_util.DATE_STR_FORMAT)
    yesterday = now - datetime.timedelta(days=1)
    yesterday_date = yesterday.strftime(dt_util.DATE_STR_FORMAT)
    tomorrow = now + datetime.timedelta(days=1)
    tomorrow_date = tomorrow.strftime(dt_util.DATE_STR_FORMAT)

    from sqlalchemy.sql import text

    # Fetch all departures for yesterday, today and optionally tomorrow,
    # up to an overkill maximum in case of a departure every minute for those
    # days.
    limit = 24 * 60 * 60 * 2
    tomorrow_select = tomorrow_where = tomorrow_order = ''
    if include_tomorrow:
        limit = int(limit / 2 * 3)
        tomorrow_name = tomorrow.strftime('%A').lower()
        tomorrow_select = "calendar.{} AS tomorrow,".format(tomorrow_name)
        tomorrow_where = "OR calendar.{} = 1".format(tomorrow_name)
        tomorrow_order = "calendar.{} DESC,".format(tomorrow_name)

    sql_query = """
        SELECT trip.trip_id, trip.route_id,
               time(origin_stop_time.arrival_time) AS origin_arrival_time,
               time(origin_stop_time.departure_time) AS origin_depart_time,
               date(origin_stop_time.departure_time) AS origin_depart_date,
               origin_stop_time.drop_off_type AS origin_drop_off_type,
               origin_stop_time.pickup_type AS origin_pickup_type,
               origin_stop_time.shape_dist_traveled AS origin_dist_traveled,
               origin_stop_time.stop_headsign AS origin_stop_headsign,
               origin_stop_time.stop_sequence AS origin_stop_sequence,
               origin_stop_time.timepoint AS origin_stop_timepoint,
               time(destination_stop_time.arrival_time) AS dest_arrival_time,
               time(destination_stop_time.departure_time) AS dest_depart_time,
               destination_stop_time.drop_off_type AS dest_drop_off_type,
               destination_stop_time.pickup_type AS dest_pickup_type,
               destination_stop_time.shape_dist_traveled AS dest_dist_traveled,
               destination_stop_time.stop_headsign AS dest_stop_headsign,
               destination_stop_time.stop_sequence AS dest_stop_sequence,
               destination_stop_time.timepoint AS dest_stop_timepoint,
               calendar.{yesterday_name} AS yesterday,
               calendar.{today_name} AS today,
               {tomorrow_select}
               calendar.start_date AS start_date,
               calendar.end_date AS end_date
        FROM trips trip
        INNER JOIN calendar calendar
                   ON trip.service_id = calendar.service_id
        INNER JOIN stop_times origin_stop_time
                   ON trip.trip_id = origin_stop_time.trip_id
        INNER JOIN stops start_station
                   ON origin_stop_time.stop_id = start_station.stop_id
        INNER JOIN stop_times destination_stop_time
                   ON trip.trip_id = destination_stop_time.trip_id
        INNER JOIN stops end_station
                   ON destination_stop_time.stop_id = end_station.stop_id
        WHERE (calendar.{yesterday_name} = 1
               OR calendar.{today_name} = 1
               {tomorrow_where}
               )
        AND start_station.stop_id = :origin_station_id
                   AND end_station.stop_id = :end_station_id
        AND origin_stop_sequence < dest_stop_sequence
        AND calendar.start_date <= :today
        AND calendar.end_date >= :today
        ORDER BY calendar.{yesterday_name} DESC,
                 calendar.{today_name} DESC,
                 {tomorrow_order}
                 origin_stop_time.departure_time
        LIMIT :limit
        """.format(yesterday_name=yesterday.strftime('%A').lower(),
                   today_name=now.strftime('%A').lower(),
                   tomorrow_select=tomorrow_select,
                   tomorrow_where=tomorrow_where,
                   tomorrow_order=tomorrow_order)
    result = schedule.engine.execute(text(sql_query),
                                     origin_station_id=start_station_id,
                                     end_station_id=end_station_id,
                                     today=now_date,
                                     limit=limit)

    # Create lookup timetable for today and possibly tomorrow, taking into
    # account any departures from yesterday scheduled after midnight,
    # as long as all departures are within the calendar date range.
    timetable = {}
    yesterday_start = today_start = tomorrow_start = None
    yesterday_last = today_last = ''

    for row in result:
        if row['yesterday'] == 1 and yesterday_date >= row['start_date']:
            extras = {
                'day': 'yesterday',
                'first': None,
                'last': False,
            }
            if yesterday_start is None:
                yesterday_start = row['origin_depart_date']
            if yesterday_start != row['origin_depart_date']:
                idx = '{} {}'.format(now_date,
                                     row['origin_depart_time'])
                timetable[idx] = {**row, **extras}
                yesterday_last = idx

        if row['today'] == 1:
            extras = {
                'day': 'today',
                'first': False,
                'last': False,
            }
            if today_start is None:
                today_start = row['origin_depart_date']
                extras['first'] = True
            if today_start == row['origin_depart_date']:
                idx_prefix = now_date
            else:
                idx_prefix = tomorrow_date
            idx = '{} {}'.format(idx_prefix, row['origin_depart_time'])
            timetable[idx] = {**row, **extras}
            today_last = idx

        if 'tomorrow' in row and row['tomorrow'] == 1 and tomorrow_date <= \
                row['end_date']:
            extras = {
                'day': 'tomorrow',
                'first': False,
                'last': None,
            }
            if tomorrow_start is None:
                tomorrow_start = row['origin_depart_date']
                extras['first'] = True
            if tomorrow_start == row['origin_depart_date']:
                idx = '{} {}'.format(tomorrow_date,
                                     row['origin_depart_time'])
                timetable[idx] = {**row, **extras}

    # Flag last departures.
    for idx in filter(None, [yesterday_last, today_last]):
        timetable[idx]['last'] = True

    _LOGGER.debug("Timetable: %s", sorted(timetable.keys()))

    item = {}  # type: dict
    for key in sorted(timetable.keys()):
        if dt_util.parse_datetime(key) > now:
            item = timetable[key]
            _LOGGER.debug("Departure found for station %s @ %s -> %s",
                          start_station_id, key, item)
            break

    if item == {}:
        return {}

    # Format arrival and departure dates and times, accounting for the
    # possibility of times crossing over midnight.
    origin_arrival = now
    if item['origin_arrival_time'] > item['origin_depart_time']:
        origin_arrival -= datetime.timedelta(days=1)
    origin_arrival_time = '{} {}'.format(
        origin_arrival.strftime(dt_util.DATE_STR_FORMAT),
        item['origin_arrival_time'])

    origin_depart_time = '{} {}'.format(now_date, item['origin_depart_time'])

    dest_arrival = now
    if item['dest_arrival_time'] < item['origin_depart_time']:
        dest_arrival += datetime.timedelta(days=1)
    dest_arrival_time = '{} {}'.format(
        dest_arrival.strftime(dt_util.DATE_STR_FORMAT),
        item['dest_arrival_time'])

    dest_depart = dest_arrival
    if item['dest_depart_time'] < item['dest_arrival_time']:
        dest_depart += datetime.timedelta(days=1)
    dest_depart_time = '{} {}'.format(
        dest_depart.strftime(dt_util.DATE_STR_FORMAT),
        item['dest_depart_time'])

    depart_time = dt_util.parse_datetime(origin_depart_time)
    arrival_time = dt_util.parse_datetime(dest_arrival_time)

    origin_stop_time = {
        'Arrival Time': origin_arrival_time,
        'Departure Time': origin_depart_time,
        'Drop Off Type': item['origin_drop_off_type'],
        'Pickup Type': item['origin_pickup_type'],
        'Shape Dist Traveled': item['origin_dist_traveled'],
        'Headsign': item['origin_stop_headsign'],
        'Sequence': item['origin_stop_sequence'],
        'Timepoint': item['origin_stop_timepoint'],
    }

    destination_stop_time = {
        'Arrival Time': dest_arrival_time,
        'Departure Time': dest_depart_time,
        'Drop Off Type': item['dest_drop_off_type'],
        'Pickup Type': item['dest_pickup_type'],
        'Shape Dist Traveled': item['dest_dist_traveled'],
        'Headsign': item['dest_stop_headsign'],
        'Sequence': item['dest_stop_sequence'],
        'Timepoint': item['dest_stop_timepoint'],
    }

    return {
        'trip_id': item['trip_id'],
        'route_id': item['route_id'],
        'day': item['day'],
        'first': item['first'],
        'last': item['last'],
        'departure_time': depart_time,
        'arrival_time': arrival_time,
        'origin_stop_time': origin_stop_time,
        'destination_stop_time': destination_stop_time,
    }


def setup_platform(hass: HomeAssistantType, config: ConfigType,
                   add_entities: Callable[[list], None],
                   discovery_info: Optional[dict] = None) -> None:
    """Set up the GTFS sensor."""
    gtfs_dir = hass.config.path(DEFAULT_PATH)
    data = config[CONF_DATA]
    origin = config.get(CONF_ORIGIN)
    destination = config.get(CONF_DESTINATION)
    name = config.get(CONF_NAME)
    offset = config.get(CONF_OFFSET)
    include_tomorrow = config[CONF_TOMORROW]

    if not os.path.exists(gtfs_dir):
        os.makedirs(gtfs_dir)

    if not os.path.exists(os.path.join(gtfs_dir, data)):
        _LOGGER.error("The given GTFS data file/folder was not found")
        return

    import pygtfs

    (gtfs_root, _) = os.path.splitext(data)

    sqlite_file = "{}.sqlite?check_same_thread=False".format(gtfs_root)
    joined_path = os.path.join(gtfs_dir, sqlite_file)
    gtfs = pygtfs.Schedule(joined_path)

    # pylint: disable=no-member
    if not gtfs.feeds:
        pygtfs.append_feed(gtfs, os.path.join(gtfs_dir, data))

    add_entities([
        GTFSDepartureSensor(gtfs, name, origin, destination, offset,
                            include_tomorrow)])


class GTFSDepartureSensor(Entity):
    """Implementation of a GTFS departure sensor."""

    def __init__(self, pygtfs: Any, name: Optional[Any], origin: Any,
                 destination: Any, offset: cv.time_period,
                 include_tomorrow: bool) -> None:
        """Initialize the sensor."""
        self._pygtfs = pygtfs
        self.origin = origin
        self.destination = destination
        self._include_tomorrow = include_tomorrow
        self._offset = offset
        self._custom_name = name

        self._available = False
        self._icon = ICON
        self._name = ''
        self._state = None  # type: Optional[str]
        self._attributes = {}  # type: dict

        self._agency = None
        self._departure = {}  # type: dict
        self._destination = None
        self._origin = None
        self._route = None
        self._trip = None

        self.lock = threading.Lock()
        self.update()

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> Optional[str]:  # type: ignore
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_class(self) -> str:
        """Return the class of this device."""
        return DEVICE_CLASS_TIMESTAMP

    def update(self) -> None:
        """Get the latest data from GTFS and update the states."""
        with self.lock:
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
                    _LOGGER.warning("Destination stop ID %s not found",
                                    self.destination)
                    return
                self._destination = stops[0]

            self._available = True

            # Fetch next departure
            self._departure = get_next_departure(
                self._pygtfs, self.origin, self.destination, self._offset,
                self._include_tomorrow)

            # Define the state as a UTC timestamp with ISO 8601 format
            if not self._departure:
                self._state = None
            else:
                self._state = dt_util.as_utc(
                    self._departure['departure_time']).isoformat()

            # Fetch trip and route details once, unless updated
            if not self._departure:
                self._trip = None
            else:
                trip_id = self._departure['trip_id']
                if not self._trip or self._trip.trip_id != trip_id:
                    _LOGGER.debug("Fetching trip details for %s", trip_id)
                    self._trip = self._pygtfs.trips_by_id(trip_id)[0]

                route_id = self._departure['route_id']
                if not self._route or self._route.route_id != route_id:
                    _LOGGER.debug("Fetching route details for %s", route_id)
                    self._route = self._pygtfs.routes_by_id(route_id)[0]

            # Fetch agency details exactly once
            if self._agency is None and self._route:
                _LOGGER.debug("Fetching agency details for %s",
                              self._route.agency_id)
                try:
                    self._agency = self._pygtfs.agencies_by_id(
                        self._route.agency_id)[0]
                except IndexError:
                    _LOGGER.warning(
                        "Agency ID '%s' was not found in agency table, "
                        "you may want to update the routes database table "
                        "to fix this missing reference",
                        self._route.agency_id)
                    self._agency = False

            # Assign attributes, icon and name
            self.update_attributes()

            if self._route:
                self._icon = ICONS.get(self._route.route_type, ICON)
            else:
                self._icon = ICON

            name = '{agency} {origin} to {destination} next departure'
            if not self._departure:
                name = '{default}'
            self._name = (self._custom_name or
                          name.format(agency=getattr(self._agency,
                                                     'agency_name',
                                                     DEFAULT_NAME),
                                      default=DEFAULT_NAME,
                                      origin=self.origin,
                                      destination=self.destination))

    def update_attributes(self) -> None:
        """Update state attributes."""
        # Add departure information
        if self._departure:
            self._attributes[ATTR_ARRIVAL] = dt_util.as_utc(
                self._departure['arrival_time']).isoformat()

            self._attributes[ATTR_DAY] = self._departure['day']

            if self._departure[ATTR_FIRST] is not None:
                self._attributes[ATTR_FIRST] = self._departure['first']
            elif ATTR_FIRST in self._attributes:
                del self._attributes[ATTR_FIRST]

            if self._departure[ATTR_LAST] is not None:
                self._attributes[ATTR_LAST] = self._departure['last']
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
        self._attributes[ATTR_OFFSET] = self._offset.seconds / 60

        if self._state is None:
            self._attributes[ATTR_INFO] = "No more departures" if \
                self._include_tomorrow else "No more departures today"
        elif ATTR_INFO in self._attributes:
            del self._attributes[ATTR_INFO]

        if self._agency:
            self._attributes[ATTR_ATTRIBUTION] = self._agency.agency_name
        elif ATTR_ATTRIBUTION in self._attributes:
            del self._attributes[ATTR_ATTRIBUTION]

        # Add extra metadata
        key = 'agency_id'
        if self._agency and key not in self._attributes:
            self.append_keys(self.dict_for_table(self._agency), 'Agency')

        key = 'origin_station_stop_id'
        if self._origin and key not in self._attributes:
            self.append_keys(self.dict_for_table(self._origin),
                             "Origin Station")
            self._attributes[ATTR_LOCATION_ORIGIN] = \
                LOCATION_TYPE_OPTIONS.get(
                    self._origin.location_type,
                    LOCATION_TYPE_DEFAULT)
            self._attributes[ATTR_WHEELCHAIR_ORIGIN] = \
                WHEELCHAIR_BOARDING_OPTIONS.get(
                    self._origin.wheelchair_boarding,
                    WHEELCHAIR_BOARDING_DEFAULT)

        key = 'destination_station_stop_id'
        if self._destination and key not in self._attributes:
            self.append_keys(self.dict_for_table(self._destination),
                             "Destination Station")
            self._attributes[ATTR_LOCATION_DESTINATION] = \
                LOCATION_TYPE_OPTIONS.get(
                    self._destination.location_type,
                    LOCATION_TYPE_DEFAULT)
            self._attributes[ATTR_WHEELCHAIR_DESTINATION] = \
                WHEELCHAIR_BOARDING_OPTIONS.get(
                    self._destination.wheelchair_boarding,
                    WHEELCHAIR_BOARDING_DEFAULT)

        # Manage Route metadata
        key = 'route_id'
        if not self._route and key in self._attributes:
            self.remove_keys('Route')
        elif self._route and (key not in self._attributes or
                              self._attributes[key] != self._route.route_id):
            self.append_keys(self.dict_for_table(self._route), 'Route')
            self._attributes[ATTR_ROUTE_TYPE] = \
                ROUTE_TYPE_OPTIONS[self._route.route_type]

        # Manage Trip metadata
        key = 'trip_id'
        if not self._trip and key in self._attributes:
            self.remove_keys('Trip')
        elif self._trip and (key not in self._attributes or
                             self._attributes[key] != self._trip.trip_id):
            self.append_keys(self.dict_for_table(self._trip), 'Trip')
            self._attributes[ATTR_BICYCLE] = BICYCLE_ALLOWED_OPTIONS.get(
                self._trip.bikes_allowed,
                BICYCLE_ALLOWED_DEFAULT)
            self._attributes[ATTR_WHEELCHAIR] = WHEELCHAIR_ACCESS_OPTIONS.get(
                self._trip.wheelchair_accessible,
                WHEELCHAIR_ACCESS_DEFAULT)

        # Manage Stop Times metadata
        prefix = 'origin_stop'
        if self._departure:
            self.append_keys(self._departure['origin_stop_time'], prefix)
            self._attributes[ATTR_DROP_OFF_ORIGIN] = DROP_OFF_TYPE_OPTIONS.get(
                self._departure['origin_stop_time']['Drop Off Type'],
                DROP_OFF_TYPE_DEFAULT)
            self._attributes[ATTR_PICKUP_ORIGIN] = PICKUP_TYPE_OPTIONS.get(
                self._departure['origin_stop_time']['Pickup Type'],
                PICKUP_TYPE_DEFAULT)
            self._attributes[ATTR_TIMEPOINT_ORIGIN] = TIMEPOINT_OPTIONS.get(
                self._departure['origin_stop_time']['Timepoint'],
                TIMEPOINT_DEFAULT)
        else:
            self.remove_keys(prefix)

        prefix = 'destination_stop'
        if self._departure:
            self.append_keys(self._departure['destination_stop_time'], prefix)
            self._attributes[ATTR_DROP_OFF_DESTINATION] = \
                DROP_OFF_TYPE_OPTIONS.get(
                    self._departure['destination_stop_time']['Drop Off Type'],
                    DROP_OFF_TYPE_DEFAULT)
            self._attributes[ATTR_PICKUP_DESTINATION] = \
                PICKUP_TYPE_OPTIONS.get(
                    self._departure['destination_stop_time']['Pickup Type'],
                    PICKUP_TYPE_DEFAULT)
            self._attributes[ATTR_TIMEPOINT_DESTINATION] = \
                TIMEPOINT_OPTIONS.get(
                    self._departure['destination_stop_time']['Timepoint'],
                    TIMEPOINT_DEFAULT)
        else:
            self.remove_keys(prefix)

    @staticmethod
    def dict_for_table(resource: Any) -> dict:
        """Return a dictionary for the SQLAlchemy resource given."""
        return dict((col, getattr(resource, col))
                    for col in resource.__table__.columns.keys())

    def append_keys(self, resource: dict, prefix: Optional[str] = None) -> \
            None:
        """Properly format key val pairs to append to attributes."""
        for attr, val in resource.items():
            if val == '' or val is None or attr == 'feed_id':
                continue
            key = attr
            if prefix and not key.startswith(prefix):
                key = '{} {}'.format(prefix, key)
            key = slugify(key)
            self._attributes[key] = val

    def remove_keys(self, prefix: str) -> None:
        """Remove attributes whose key starts with prefix."""
        self._attributes = {k: v for k, v in self._attributes.items() if
                            not k.startswith(prefix)}
