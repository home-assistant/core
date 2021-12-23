"""Train information for departures and delays, provided by Trafikverket."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging

from pytrafikverket import TrafikverketTrain
from pytrafikverket.trafikverket_train import TrainStop
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_WEEKDAY, WEEKDAYS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.dt import as_utc, get_time_zone

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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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


def next_weekday(fromdate: date, weekday: int) -> date:
    """Return the date of the next time a specific weekday happen."""
    days_ahead = weekday - fromdate.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return fromdate + timedelta(days_ahead)


def next_departuredate(departure: list) -> date:
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


class TrainSensor(SensorEntity):
    """Contains data about a train depature."""

    _attr_icon = ICON
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        train_api: TrafikverketTrain,
        name: str,
        from_station: str,
        to_station: str,
        weekday: list,
        departuretime: time,
    ) -> None:
        """Initialize the sensor."""
        self._train_api = train_api
        self._attr_name = name
        self._from_station = from_station
        self._to_station = to_station
        self._weekday = weekday
        self._time = departuretime
        self._state: TrainStop | None = None
        self._delay_in_minutes: timedelta | None = None
        self._timezone = get_time_zone("Europe/Stockholm")
        self._attr_extra_state_attributes = {}

    async def async_update(self) -> None:
        """Retrieve latest state."""
        try:
            if self._time:
                departure_day = next_departuredate(self._weekday)
                when = datetime.combine(departure_day, self._time).astimezone(
                    self._timezone
                )
                self._state = await self._train_api.async_get_train_stop(
                    self._from_station, self._to_station, when
                )
            else:
                when = datetime.now()
                self._state = await self._train_api.async_get_next_train_stop(
                    self._from_station, self._to_station, when
                )
        except ValueError as output_error:
            _LOGGER.error("Departure %s encountered a problem: %s", when, output_error)

        if not self._state:
            self._attr_available = False
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return

        self._attr_available = True

        self._attr_native_value = self._state.advertised_time_at_location.astimezone(
            self._timezone
        )
        if self._state.time_at_location:
            self._attr_native_value = self._state.time_at_location.astimezone(
                self._timezone
            )
        if self._state.estimated_time_at_location:
            self._attr_native_value = self._state.estimated_time_at_location.astimezone(
                self._timezone
            )

        self._attr_extra_state_attributes[ATTR_DEPARTURE_STATE] = (
            self._state.get_state().name if self._state.get_state().name else None
        )
        self._attr_extra_state_attributes[ATTR_CANCELED] = (
            self._state.canceled if self._state.canceled else None
        )
        self._delay_in_minutes = self._state.get_delay_time()
        self._attr_extra_state_attributes[ATTR_DELAY_TIME] = (
            self._delay_in_minutes.total_seconds() / 60
            if self._delay_in_minutes
            else None
        )
        self._attr_extra_state_attributes[ATTR_PLANNED_TIME] = (
            as_utc(
                self._state.advertised_time_at_location.astimezone(self._timezone)
            ).isoformat()
            if self._state.advertised_time_at_location
            else None
        )
        self._attr_extra_state_attributes[ATTR_ESTIMATED_TIME] = (
            as_utc(
                self._state.estimated_time_at_location.astimezone(self._timezone)
            ).isoformat()
            if self._state.estimated_time_at_location
            else None
        )
        self._attr_extra_state_attributes[ATTR_ACTUAL_TIME] = (
            as_utc(self._state.time_at_location.astimezone(self._timezone)).isoformat()
            if self._state.time_at_location
            else None
        )
        self._attr_extra_state_attributes[ATTR_OTHER_INFORMATION] = (
            ", ".join(self._state.other_information)
            if self._state.other_information
            else None
        )
        self._attr_extra_state_attributes[ATTR_DEVIATIONS] = (
            ", ".join(self._state.deviations) if self._state.deviations else None
        )
