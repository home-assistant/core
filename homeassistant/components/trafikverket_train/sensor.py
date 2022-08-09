"""Train information for departures and delays, provided by Trafikverket."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging
from typing import Any

from pytrafikverket import TrafikverketTrain
from pytrafikverket.trafikverket_train import StationInfo, TrainStop

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_WEEKDAY, WEEKDAYS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt

from .const import CONF_FROM, CONF_TIME, CONF_TO, DOMAIN
from .util import create_unique_id

_LOGGER = logging.getLogger(__name__)

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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Trafikverket sensor entry."""

    train_api = hass.data[DOMAIN][entry.entry_id]["train_api"]
    to_station = hass.data[DOMAIN][entry.entry_id][CONF_TO]
    from_station = hass.data[DOMAIN][entry.entry_id][CONF_FROM]
    get_time: str | None = entry.data.get(CONF_TIME)
    train_time = dt.parse_time(get_time) if get_time else None

    async_add_entities(
        [
            TrainSensor(
                train_api,
                entry.data[CONF_NAME],
                from_station,
                to_station,
                entry.data[CONF_WEEKDAY],
                train_time,
                entry.entry_id,
            )
        ],
        True,
    )


def next_weekday(fromdate: date, weekday: int) -> date:
    """Return the date of the next time a specific weekday happen."""
    days_ahead = weekday - fromdate.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return fromdate + timedelta(days_ahead)


def next_departuredate(departure: list[str]) -> date:
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


def _to_iso_format(traintime: datetime) -> str:
    """Return isoformatted utc time."""
    return dt.as_utc(traintime).isoformat()


class TrainSensor(SensorEntity):
    """Contains data about a train depature."""

    _attr_icon = ICON
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        train_api: TrafikverketTrain,
        name: str,
        from_station: StationInfo,
        to_station: StationInfo,
        weekday: list,
        departuretime: time | None,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        self._train_api = train_api
        self._attr_name = name
        self._from_station = from_station
        self._to_station = to_station
        self._weekday = weekday
        self._time = departuretime
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Trafikverket",
            model="v2.0",
            name=name,
            configuration_url="https://api.trafikinfo.trafikverket.se/",
        )
        self._attr_unique_id = create_unique_id(
            from_station.name, to_station.name, departuretime, weekday
        )

    async def async_update(self) -> None:
        """Retrieve latest state."""
        when = dt.now()
        _state: TrainStop | None = None
        if self._time:
            departure_day = next_departuredate(self._weekday)
            when = datetime.combine(
                departure_day, self._time, dt.get_time_zone(self.hass.config.time_zone)
            )
        try:
            if self._time:
                _state = await self._train_api.async_get_train_stop(
                    self._from_station, self._to_station, when
                )
            else:

                _state = await self._train_api.async_get_next_train_stop(
                    self._from_station, self._to_station, when
                )
        except ValueError as error:
            _LOGGER.error("Departure %s encountered a problem: %s", when, error)

        if not _state:
            self._attr_available = False
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return

        self._attr_available = True

        # The original datetime doesn't provide a timezone so therefore attaching it here.
        self._attr_native_value = dt.as_utc(_state.advertised_time_at_location)
        if _state.time_at_location:
            self._attr_native_value = dt.as_utc(_state.time_at_location)
        if _state.estimated_time_at_location:
            self._attr_native_value = dt.as_utc(_state.estimated_time_at_location)

        self._update_attributes(_state)

    def _update_attributes(self, state: TrainStop) -> None:
        """Return extra state attributes."""

        attributes: dict[str, Any] = {
            ATTR_DEPARTURE_STATE: state.get_state().name,
            ATTR_CANCELED: state.canceled,
            ATTR_DELAY_TIME: None,
            ATTR_PLANNED_TIME: None,
            ATTR_ESTIMATED_TIME: None,
            ATTR_ACTUAL_TIME: None,
            ATTR_OTHER_INFORMATION: None,
            ATTR_DEVIATIONS: None,
        }

        if delay_in_minutes := state.get_delay_time():
            attributes[ATTR_DELAY_TIME] = delay_in_minutes.total_seconds() / 60

        if advert_time := state.advertised_time_at_location:
            attributes[ATTR_PLANNED_TIME] = _to_iso_format(advert_time)

        if est_time := state.estimated_time_at_location:
            attributes[ATTR_ESTIMATED_TIME] = _to_iso_format(est_time)

        if time_location := state.time_at_location:
            attributes[ATTR_ACTUAL_TIME] = _to_iso_format(time_location)

        if other_info := state.other_information:
            attributes[ATTR_OTHER_INFORMATION] = ", ".join(other_info)

        if deviation := state.deviations:
            attributes[ATTR_DEVIATIONS] = ", ".join(deviation)

        self._attr_extra_state_attributes = attributes
