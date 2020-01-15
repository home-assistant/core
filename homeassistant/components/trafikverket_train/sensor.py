"""Train information for departures and delays, provided by Trafikverket."""

from datetime import date, datetime, timedelta
import logging

from pytrafikverket import TrafikverketTrain
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_WEEKDAY,
    DEVICE_CLASS_TIMESTAMP,
    WEEKDAYS,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_TRAINS = "trains"
CONF_FROM = "from"
CONF_TO = "to"
CONF_TIME = "time"

ATTR_DEPARTURE_STATE = "departure_state"
ATTR_CANCELED = "canceled"
ATTR_DELAY_TIME = "number_of_minutes_delayed"
ATTR_PLANNED_TIME = "planned_time"
ATTR_ESTIMATED_TIME = "estimated_time"
ATTR_ACTUAL_TIME = "actual_time"
ATTR_OTHER_INFORMATION = "other_information"
ATTR_DEVIATIONS = "deviations"

ICON = "mdi:train"
SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_TRAINS): [
            {
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_TO): cv.string,
                vol.Required(CONF_FROM): cv.string,
                vol.Optional(CONF_TIME): cv.time,
                vol.Optional(CONF_WEEKDAY, default=WEEKDAYS): vol.All(
                    cv.ensure_list, [vol.In(WEEKDAYS)]
                ),
            }
        ],
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the departure sensor."""
    httpsession = async_get_clientsession(hass)
    train_api = TrafikverketTrain(httpsession, config[CONF_API_KEY])
    sensors = []
    station_cache = {}
    for train in config[CONF_TRAINS]:
        try:
            trainstops = [train[CONF_FROM], train[CONF_TO]]
            for station in trainstops:
                if station not in station_cache:
                    station_cache[station] = await train_api.async_get_train_station(
                        station
                    )

        except ValueError as station_error:
            if "Invalid authentication" in station_error.args[0]:
                _LOGGER.error("Unable to set up up component: %s", station_error)
                return
            _LOGGER.error(
                "Problem when trying station %s to %s. Error: %s ",
                train[CONF_FROM],
                train[CONF_TO],
                station_error,
            )
            continue

        sensor = TrainSensor(
            train_api,
            train[CONF_NAME],
            station_cache[train[CONF_FROM]],
            station_cache[train[CONF_TO]],
            train[CONF_WEEKDAY],
            train.get(CONF_TIME),
        )
        sensors.append(sensor)

    async_add_entities(sensors, update_before_add=True)


def next_weekday(fromdate, weekday):
    """Return the date of the next time a specific weekday happen."""
    days_ahead = weekday - fromdate.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return fromdate + timedelta(days_ahead)


def next_departuredate(departure):
    """Calculate the next departuredate from an array input of short days."""
    today_date = date.today()
    today_weekday = date.weekday(today_date)
    if WEEKDAYS[today_weekday] in departure:
        return today_date
    for day in departure:
        next_departure = WEEKDAYS.index(day)
        if next_departure > today_weekday:
            return next_weekday(today_date, next_departure)
    return next_weekday(today_date, WEEKDAYS.index(departure[0]))


class TrainSensor(Entity):
    """Contains data about a train depature."""

    def __init__(self, train_api, name, from_station, to_station, weekday, time):
        """Initialize the sensor."""
        self._train_api = train_api
        self._name = name
        self._from_station = from_station
        self._to_station = to_station
        self._weekday = weekday
        self._time = time
        self._state = None
        self._departure_state = None
        self._delay_in_minutes = None

    async def async_update(self):
        """Retrieve latest state."""
        if self._time is not None:
            departure_day = next_departuredate(self._weekday)
            when = datetime.combine(departure_day, self._time)
            try:
                self._state = await self._train_api.async_get_train_stop(
                    self._from_station, self._to_station, when
                )
            except ValueError as output_error:
                _LOGGER.error(
                    "Departure %s encountered a problem: %s", when, output_error
                )
        else:
            when = datetime.now()
            self._state = await self._train_api.async_get_next_train_stop(
                self._from_station, self._to_station, when
            )
        self._departure_state = self._state.get_state().name
        self._delay_in_minutes = self._state.get_delay_time()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._state is None:
            return None
        state = self._state
        other_information = None
        if state.other_information is not None:
            other_information = ", ".join(state.other_information)
        deviations = None
        if state.deviations is not None:
            deviations = ", ".join(state.deviations)
        if self._delay_in_minutes is not None:
            self._delay_in_minutes = self._delay_in_minutes.total_seconds() / 60
        return {
            ATTR_DEPARTURE_STATE: self._departure_state,
            ATTR_CANCELED: state.canceled,
            ATTR_DELAY_TIME: self._delay_in_minutes,
            ATTR_PLANNED_TIME: state.advertised_time_at_location,
            ATTR_ESTIMATED_TIME: state.estimated_time_at_location,
            ATTR_ACTUAL_TIME: state.time_at_location,
            ATTR_OTHER_INFORMATION: other_information,
            ATTR_DEVIATIONS: deviations,
        }

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the frontend."""
        return ICON

    @property
    def state(self):
        """Return the departure state."""
        state = self._state
        if state is not None:
            if state.time_at_location is not None:
                return state.time_at_location
            if state.estimated_time_at_location is not None:
                return state.estimated_time_at_location
            return state.advertised_time_at_location
        return None
