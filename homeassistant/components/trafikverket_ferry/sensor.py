"""Train information for departures and delays, provided by Trafikverket."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging

from pytrafikverket import TrafikverketFerry
from pytrafikverket.trafikverket_ferry import FerryStop

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_WEEKDAY, WEEKDAYS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import UTC, as_utc, parse_time

from .const import CONF_FROM, CONF_TIME, CONF_TO, DOMAIN
from .util import create_unique_id

_LOGGER = logging.getLogger(__name__)

ATTR_FROM = "from_harbour"
ATTR_TO = "to_harbour"
ATTR_MODIFIED_TIME = "modified_time"
ATTR_OTHER_INFO = "other_info"

ICON = "mdi:ferry"
SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Trafikverket sensor entry."""

    httpsession = async_get_clientsession(hass)
    ferry_api = TrafikverketFerry(httpsession, entry.data[CONF_API_KEY])

    try:
        await ferry_api.async_get_next_ferry_stop(entry.data[CONF_FROM])
    except ValueError as error:
        if "Invalid authentication" in error.args[0]:
            raise ConfigEntryAuthFailed from error
        raise ConfigEntryNotReady(
            f"Problem when trying station {entry.data[CONF_FROM]} to {entry.data[CONF_TO]}. Error: {error} "
        ) from error

    ferry_time = parse_time(entry.data[CONF_TIME])

    async_add_entities(
        [
            FerrySensor(
                ferry_api,
                entry.data[CONF_NAME],
                entry.data[CONF_FROM],
                entry.data[CONF_TO],
                entry.data[CONF_WEEKDAY],
                ferry_time,
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
    return as_utc(traintime.replace(tzinfo=UTC)).isoformat()


class FerrySensor(SensorEntity):
    """Contains data about a train depature."""

    _attr_icon = ICON
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        ferry_api: TrafikverketFerry,
        name: str,
        ferry_from: str,
        ferry_to: str,
        weekday: list,
        departuretime: time | None,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        self._ferry_api = ferry_api
        self._attr_name = name
        self._ferry_from = ferry_from
        self._ferry_to = ferry_to
        self._weekday = weekday
        self._time = departuretime
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Trafikverket",
            model="v1.2",
            name=name,
            configuration_url="https://api.trafikinfo.trafikverket.se/",
        )
        self._attr_unique_id = create_unique_id(
            ferry_from, ferry_to, departuretime, weekday
        )

    async def async_update(self) -> None:
        """Retrieve latest state."""
        when = datetime.now()
        _state: FerryStop | None = None
        if self._time:
            departure_day = next_departuredate(self._weekday)
            when = datetime.combine(departure_day, self._time)
        try:
            if self._time:
                _state = await self._ferry_api.async_get_next_ferry_stop(
                    self._ferry_from, self._ferry_to, when
                )
            else:

                _state = await self._ferry_api.async_get_next_ferry_stop(
                    self._ferry_from, self._ferry_to, when
                )
        except ValueError as output_error:
            _LOGGER.error("Departure %s encountered a problem: %s", when, output_error)

        if not _state:
            self._attr_available = False
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return

        self._attr_available = True

        self._attr_native_value = _state.departure_time.replace(tzinfo=UTC)

        self._attr_extra_state_attributes = {
            ATTR_FROM: _state.from_harbor_name,
            ATTR_TO: _state.to_harbor_name,
            ATTR_MODIFIED_TIME: _to_iso_format(_state.modified_time),
            ATTR_OTHER_INFO: _state.other_information,
        }
