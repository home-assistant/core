"""Train information for departures and delays, provided by Trafikverket."""

import asyncio
from datetime import date, datetime, timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_WEEKDAY, WEEKDAYS
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_TRAINS = "trains"
CONF_FROM = "from"
CONF_TO = "to"
CONF_TIME = "time"

ATTR_CANCELED = "canceled"
ATTR_DELAY_TIME = "number_of_minutes_delayed"
ATTR_PLANNED_TIME = "planned_time"
ATTR_ESTIMATED_TIME = "estimated_time"
ATTR_ACTUAL_TIME = "actual_time"
ATTR_OTHER_INFORMATION = "other_information"
ATTR_DEVIATIONS = "deviations"

ICON = "mdi:train"
SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_TRAINS): [{
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_TO): cv.string,
        vol.Required(CONF_FROM): cv.string,
        vol.Optional(CONF_TIME): cv.time,
        vol.Optional(CONF_WEEKDAY, default=WEEKDAYS):
            vol.All(cv.ensure_list, [vol.In(WEEKDAYS)])}]
})


@asyncio.coroutine
def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Set up the departure sensor."""
    from pytrafikverket import TrafikverketTrain
    httpsession = async_get_clientsession(hass)
    train_api = TrafikverketTrain(httpsession, config.get(CONF_API_KEY))
    sensors = []
    for train in config.get(CONF_TRAINS):
        try:
            from_station = yield from train_api.async_get_train_station(
                train.get(CONF_FROM))
            to_station = yield from train_api.async_get_train_station(
                train.get(CONF_TO))
        except ValueError as station_error:
            _LOGGER.error("Problem when trying station %s to %s. Error: %s ",
                          train.get(CONF_FROM), train.get(CONF_TO),
                          station_error)
            return

        sensor = TrainSensor(train_api,
                             train.get(CONF_NAME),
                             from_station,
                             to_station,
                             train.get(CONF_WEEKDAY),
                             train.get(CONF_TIME))
        sensors.append(sensor)

    async_add_devices(sensors, update_before_add=True)


def next_weekday(fromdate, weekday):
    """Return the date of the next time a specific weekday happen."""
    days_ahead = weekday - fromdate.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return fromdate + timedelta(days_ahead)


def next_departuredate(departure):
    """Calculate the next departuredate from an array input of short days."""
    today_weekday = date.weekday(date.today())
    today_date = date.today()
    if WEEKDAYS[today_weekday] in departure:
        return date.today()
    for day in departure:
        next_departure = WEEKDAYS.index(day)
        if next_departure > today_weekday:
            return next_weekday(today_date, next_departure)
    return next_weekday(today_date, WEEKDAYS.index(departure[0]))


class TrainSensor(Entity):
    """Contains data about a train depature."""

    def __init__(self, train_api, name,
                 from_station, to_station, weekday, time):
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

    @asyncio.coroutine
    def async_update(self):
        """Retrieve latest state."""
        departure_day = next_departuredate(self._weekday)
        if self._time is not None:
            when = datetime.combine(departure_day, self._time)
            try:
                self._state = yield from \
                    self._train_api.async_get_train_stop(
                        self._from_station, self._to_station, when)
            except ValueError as output_error:
                _LOGGER.error("Departure %s encountered a problem: %s",
                              when, output_error)
        else:
            when = datetime.now()
            self._state = yield from \
                self._train_api.async_get_next_train_stop(
                    self._from_station, self._to_station, when)
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
            self._delay_in_minutes = \
                self._delay_in_minutes.total_seconds() / 60
        return {ATTR_CANCELED: state.canceled,
                ATTR_DELAY_TIME: self._delay_in_minutes,
                ATTR_PLANNED_TIME: state.advertised_time_at_location,
                ATTR_ESTIMATED_TIME: state.estimated_time_at_location,
                ATTR_ACTUAL_TIME: state.time_at_location,
                ATTR_OTHER_INFORMATION: other_information,
                ATTR_DEVIATIONS: deviations}

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
        if self._state is not None:
            return self._departure_state
        return None
