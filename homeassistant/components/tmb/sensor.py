"""Support for TMB (Transports Metropolitans de Barcelona) Barcelona public transport."""
from datetime import timedelta
import logging

from requests import HTTPError
from tmb import IBus, Planner
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_NAME,
    ATTR_SECONDS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    TIME_MINUTES,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by Transports Metropolitans de Barcelona - tmb.cat"

"""
sensor:
- platform: tmb
  app_id: !secret tmb_app_id
  app_key: !secret tmb_app_key
  stops:
    - line: V25
      stop: 3258
  routes:
    - name: From home to work
      from:
        latitude: 41.3755204
        longitude: 2.1498870
      to:
        latitude: 41.3878951
        longitude: 2.1308587
"""

ATTR_BUS_STOP = "stop"
ATTR_DESCRIPTION = "description"
ATTR_IN_TRANSIT = "time in transit"
ATTR_LINE = "line"
ATTR_TRANSFERS = "num transfers"
ATTR_WAITING = "time waiting"
ATTR_WALK_DISTANCE = "walk distance"
CONF_APP_ID = "app_id"
CONF_APP_KEY = "app_key"
CONF_BUS_STOP = "stop"
CONF_BUS_STOPS = "stops"
CONF_LINE = "line"
CONF_ROUTES = "routes"
CONF_ROUTE_FROM = "from"
CONF_ROUTE_TO = "to"
ICON_IBUS = "mdi:bus-clock"
ICON_PLANNER = "mdi:map-marker-distance"

MIN_TIME_BETWEEN_UPDATES_IBUS = timedelta(seconds=60)
MIN_TIME_BETWEEN_UPDATES_PLANNER = timedelta(seconds=300)

LINE_STOP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BUS_STOP): cv.string,
        vol.Required(CONF_LINE): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)

ROUTES_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ROUTE_FROM): vol.Schema(
            {
                vol.Required(CONF_LATITUDE): cv.latitude,
                vol.Required(CONF_LONGITUDE): cv.longitude,
            }
        ),
        vol.Required(CONF_ROUTE_TO): vol.Schema(
            {
                vol.Required(CONF_LATITUDE): cv.latitude,
                vol.Required(CONF_LONGITUDE): cv.longitude,
            }
        ),
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_APP_ID): cv.string,
        vol.Required(CONF_APP_KEY): cv.string,
        vol.Optional(CONF_BUS_STOPS): vol.All(cv.ensure_list, [LINE_STOP_SCHEMA]),
        vol.Optional(CONF_ROUTES): vol.All(cv.ensure_list, [ROUTES_SCHEMA]),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensors."""
    ibus_client = IBus(config[CONF_APP_ID], config[CONF_APP_KEY])
    planner_client = Planner(config[CONF_APP_ID], config[CONF_APP_KEY])

    sensors = []

    # TMB iBus sensors
    if config.get(CONF_BUS_STOPS) is not None:
        for line_stop in config.get(CONF_BUS_STOPS):
            line = line_stop[CONF_LINE]
            stop = line_stop[CONF_BUS_STOP]
            if line_stop.get(CONF_NAME):
                name = f"{line} - {line_stop[CONF_NAME]} ({stop})"
            else:
                name = f"{line} - {stop}"

            sensors.append(TMBIBusSensor(ibus_client, stop, line, name))

    # TMB Planner sensors
    if config.get(CONF_ROUTES) is not None:
        for route in config.get(CONF_ROUTES):
            from_lat = route[CONF_ROUTE_FROM][CONF_LATITUDE]
            from_lon = route[CONF_ROUTE_FROM][CONF_LONGITUDE]
            from_latlon = f"{from_lat},{from_lon}"

            to_lat = route[CONF_ROUTE_TO][CONF_LATITUDE]
            to_lon = route[CONF_ROUTE_TO][CONF_LONGITUDE]
            to_latlon = f"{to_lat},{to_lon}"
            name = route[CONF_NAME]

            sensors.append(
                TMBPlannerSensor(planner_client, from_latlon, to_latlon, name)
            )

    add_entities(sensors, True)


class TMBIBusSensor(Entity):
    """Implementation of a TMB line/stop Sensor."""

    def __init__(self, ibus_client, stop, line, name):
        """Initialize the sensor."""
        self._ibus_client = ibus_client
        self._stop = stop
        self._line = line.upper()
        self._name = name
        self._unit = TIME_MINUTES
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON_IBUS

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return f"{self._stop}_{self._line}"

    @property
    def state(self):
        """Return the next departure time."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the last update."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_BUS_STOP: self._stop,
            ATTR_LINE: self._line,
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES_IBUS)
    def update(self):
        """Get the next bus information."""
        try:
            self._state = self._ibus_client.get_stop_forecast(self._stop, self._line)
        except HTTPError:
            _LOGGER.error(
                "Unable to fetch data from TMB API. Please check your API keys are valid"
            )


class TMBPlannerSensor(Entity):
    """Implementation of a TMB line/stop Sensor."""

    def __init__(self, planner_client, from_coords, to_coords, name):
        """Initialize the sensor."""
        self._planner_client = planner_client
        self._from_coords = from_coords
        self._to_coords = to_coords
        self._unit = TIME_MINUTES
        self._name = name
        self._attr_description = None
        self._attr_durationInSeconds = None
        self._attr_transitTime = None
        self._attr_waitingTime = None
        self._attr_walkDistance = None
        self._attr_transfers = None
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON_PLANNER

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return f"tmb_planner_{self._name}"

    @property
    def state(self):
        """Return the next departure time."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the last update."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_NAME: self._name,
            ATTR_DESCRIPTION: self._attr_description,
            ATTR_SECONDS: self._attr_durationInSeconds,
            ATTR_IN_TRANSIT: self._attr_transitTime,
            ATTR_WAITING: self._attr_waitingTime,
            ATTR_WALK_DISTANCE: self._attr_walkDistance,
            ATTR_TRANSFERS: self._attr_transfers,
        }

    @Throttle(MIN_TIME_BETWEEN_UPDATES_PLANNER)
    def update(self):
        """Get the next bus information."""
        try:
            plan = self._planner_client.get_shortest_itinerary(
                self._from_coords, self._to_coords
            )
            self._state = plan["durationInMinutes"]
            self._attr_description = plan["description"]
            self._attr_durationInSeconds = plan["durationInSeconds"]
            self._attr_transitTime = plan["transitTime"]
            self._attr_waitingTime = plan["waitingTime"]
            self._attr_walkDistance = plan["walkDistance"]
            self._attr_transfers = plan["transfers"]

        except HTTPError:
            _LOGGER.error(
                "Unable to fetch data from TMB API. Please check your API keys."
            )
