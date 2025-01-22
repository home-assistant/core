"""DataUpdateCoordinator for the Trafikverket Train integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
import logging
from typing import TYPE_CHECKING

from pytrafikverket import (
    InvalidAuthentication,
    MultipleTrainStationsFound,
    NoTrainAnnouncementFound,
    NoTrainStationFound,
    StationInfoModel,
    TrafikverketTrain,
    TrainStopModel,
    UnknownError,
)

from homeassistant.const import CONF_API_KEY, CONF_WEEKDAY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_FILTER_PRODUCT, CONF_FROM, CONF_TIME, CONF_TO, DOMAIN
from .util import next_departuredate

if TYPE_CHECKING:
    from . import TVTrainConfigEntry


@dataclass
class TrainData:
    """Dataclass for Trafikverket Train data."""

    departure_time: datetime | None
    departure_state: str
    cancelled: bool | None
    delayed_time: int | None
    planned_time: datetime | None
    estimated_time: datetime | None
    actual_time: datetime | None
    other_info: str | None
    deviation: str | None
    product_filter: str | None
    departure_time_next: datetime | None
    departure_time_next_next: datetime | None


_LOGGER = logging.getLogger(__name__)
TIME_BETWEEN_UPDATES = timedelta(minutes=5)


def _get_as_utc(date_value: datetime | None) -> datetime | None:
    """Return utc datetime or None."""
    if date_value:
        return dt_util.as_utc(date_value)
    return None


def _get_as_joined(information: list[str] | None) -> str | None:
    """Return joined information or None."""
    if information:
        return ", ".join(information)
    return None


class TVDataUpdateCoordinator(DataUpdateCoordinator[TrainData]):
    """A Trafikverket Data Update Coordinator."""

    config_entry: TVTrainConfigEntry
    from_station: StationInfoModel
    to_station: StationInfoModel

    def __init__(self, hass: HomeAssistant, config_entry: TVTrainConfigEntry) -> None:
        """Initialize the Trafikverket coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=TIME_BETWEEN_UPDATES,
        )
        self._train_api = TrafikverketTrain(
            async_get_clientsession(hass), config_entry.data[CONF_API_KEY]
        )
        self._time: time | None = dt_util.parse_time(config_entry.data[CONF_TIME])
        self._weekdays: list[str] = config_entry.data[CONF_WEEKDAY]
        self._filter_product: str | None = config_entry.options.get(CONF_FILTER_PRODUCT)

    async def _async_setup(self) -> None:
        """Initiate stations."""
        try:
            self.to_station = (
                await self._train_api.async_get_train_station_from_signature(
                    self.config_entry.data[CONF_TO]
                )
            )
            self.from_station = (
                await self._train_api.async_get_train_station_from_signature(
                    self.config_entry.data[CONF_FROM]
                )
            )
        except InvalidAuthentication as error:
            raise ConfigEntryAuthFailed from error
        except (NoTrainStationFound, MultipleTrainStationsFound) as error:
            raise UpdateFailed(
                f"Problem when trying station {self.config_entry.data[CONF_FROM]} to"
                f" {self.config_entry.data[CONF_TO]}. Error: {error} "
            ) from error

    async def _async_update_data(self) -> TrainData:
        """Fetch data from Trafikverket."""

        when = dt_util.now()
        state: TrainStopModel | None = None
        states: list[TrainStopModel] | None = None
        if self._time:
            departure_day = next_departuredate(self._weekdays)
            when = datetime.combine(
                departure_day,
                self._time,
                dt_util.get_default_time_zone(),
            )
        try:
            if self._time:
                state = await self._train_api.async_get_train_stop(
                    self.from_station, self.to_station, when, self._filter_product
                )
            else:
                states = await self._train_api.async_get_next_train_stops(
                    self.from_station,
                    self.to_station,
                    when,
                    self._filter_product,
                    number_of_stops=3,
                )
        except InvalidAuthentication as error:
            raise ConfigEntryAuthFailed from error
        except (
            NoTrainAnnouncementFound,
            UnknownError,
        ) as error:
            raise UpdateFailed(
                f"Train departure {when} encountered a problem: {error}"
            ) from error

        depart_next = None
        depart_next_next = None
        if not state and states:
            state = states[0]
            depart_next = (
                states[1].advertised_time_at_location if len(states) > 1 else None
            )
            depart_next_next = (
                states[2].advertised_time_at_location if len(states) > 2 else None
            )

        if not state:
            raise UpdateFailed("Could not find any departures")

        departure_time = state.advertised_time_at_location
        if state.estimated_time_at_location:
            departure_time = state.estimated_time_at_location
        elif state.time_at_location:
            departure_time = state.time_at_location

        delay_time = state.get_delay_time()

        return TrainData(
            departure_time=_get_as_utc(departure_time),
            departure_state=state.get_state().value,
            cancelled=state.canceled,
            delayed_time=delay_time.seconds if delay_time else None,
            planned_time=_get_as_utc(state.advertised_time_at_location),
            estimated_time=_get_as_utc(state.estimated_time_at_location),
            actual_time=_get_as_utc(state.time_at_location),
            other_info=_get_as_joined(state.other_information),
            deviation=_get_as_joined(state.deviations),
            product_filter=self._filter_product,
            departure_time_next=_get_as_utc(depart_next),
            departure_time_next_next=_get_as_utc(depart_next_next),
        )
