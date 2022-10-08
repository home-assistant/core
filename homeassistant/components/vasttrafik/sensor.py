"""Support for Västtrafik public transport."""
from __future__ import annotations

from datetime import timedelta
import logging

import vasttrafik
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION, CONF_DELAY, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
from homeassistant.util.dt import now

_LOGGER = logging.getLogger(__name__)

ATTR_ACCESSIBILITY = "accessibility"
ATTR_DIRECTION = "direction"
ATTR_LINE = "line"
ATTR_TRACK = "track"
ATTRIBUTION = "Data provided by Västtrafik"

CONF_DEPARTURES = "departures"
CONF_FROM = "from"
CONF_HEADING = "heading"
CONF_LINES = "lines"
CONF_KEY = "key"
CONF_SECRET = "secret"

DEFAULT_DELAY = 0

ICON = "mdi:train"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=120)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_KEY): cv.string,
        vol.Required(CONF_SECRET): cv.string,
        vol.Required(CONF_DEPARTURES): [
            {
                vol.Required(CONF_FROM): cv.string,
                vol.Optional(CONF_DELAY, default=DEFAULT_DELAY): cv.positive_int,
                vol.Optional(CONF_HEADING): cv.string,
                vol.Optional(CONF_LINES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(CONF_NAME): cv.string,
            }
        ],
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the departure sensor."""
    planner = vasttrafik.JournyPlanner(config.get(CONF_KEY), config.get(CONF_SECRET))
    sensors = []

    for departure in config[CONF_DEPARTURES]:
        sensors.append(
            VasttrafikDepartureSensor(
                planner,
                departure.get(CONF_NAME),
                departure.get(CONF_FROM),
                departure.get(CONF_HEADING),
                departure.get(CONF_LINES),
                departure.get(CONF_DELAY),
            )
        )
    add_entities(sensors, True)


class VasttrafikDepartureSensor(SensorEntity):
    """Implementation of a Vasttrafik Departure Sensor."""

    def __init__(self, planner, name, departure, heading, lines, delay):
        """Initialize the sensor."""
        self._planner = planner
        self._name = name or departure
        self._departure = self.get_station_id(departure)
        self._heading = self.get_station_id(heading) if heading else None
        self._lines = lines if lines else None
        self._delay = timedelta(minutes=delay)
        self._departureboard = None
        self._state = None
        self._attributes = None

    def get_station_id(self, location):
        """Get the station ID."""
        if location.isdecimal():
            station_info = {"station_name": location, "station_id": location}
        else:
            station_id = self._planner.location_name(location)[0]["id"]
            station_info = {"station_name": location, "station_id": station_id}
        return station_info

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def native_value(self):
        """Return the next departure time."""
        return self._state

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Get the departure board."""
        try:
            self._departureboard = self._planner.departureboard(
                self._departure["station_id"],
                direction=self._heading["station_id"] if self._heading else None,
                date=now() + self._delay,
            )
        except vasttrafik.Error:
            _LOGGER.debug("Unable to read departure board, updating token")
            self._planner.update_token()

        if not self._departureboard:
            _LOGGER.debug(
                "No departures from departure station %s to destination station %s",
                self._departure["station_name"],
                self._heading["station_name"] if self._heading else "ANY",
            )
            self._state = None
            self._attributes = {}
        else:
            for departure in self._departureboard:
                line = departure.get("sname")
                if "cancelled" in departure:
                    continue
                if not self._lines or line in self._lines:
                    if "rtTime" in departure:
                        self._state = departure["rtTime"]
                    else:
                        self._state = departure["time"]

                    params = {
                        ATTR_ACCESSIBILITY: departure.get("accessibility"),
                        ATTR_ATTRIBUTION: ATTRIBUTION,
                        ATTR_DIRECTION: departure.get("direction"),
                        ATTR_LINE: departure.get("sname"),
                        ATTR_TRACK: departure.get("track"),
                    }

                    self._attributes = {k: v for k, v in params.items() if v}
                    break
