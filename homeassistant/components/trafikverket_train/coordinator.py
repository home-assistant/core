"""DataUpdateCoordinator for the Trafikverket Train integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
import logging
from typing import TYPE_CHECKING

from pytrafikverket import TrafikverketTrain
from pytrafikverket.exceptions import (
    InvalidAuthentication,
    NoTrainAnnouncementFound,
    UnknownError,
)
from pytrafikverket.models import StationInfoModel, TrainStopModel

from homeassistant.const import CONF_API_KEY, CONF_WEEKDAY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_FILTER_PRODUCT, CONF_TIME, DOMAIN
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

    def __init__(
        self,
        hass: HomeAssistant,
        to_station: StationInfoModel,
        from_station: StationInfoModel,
    ) -> None:
        """Initialize the Trafikverket coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=TIME_BETWEEN_UPDATES,
        )
        self._train_api = TrafikverketTrain(
            async_get_clientsession(hass), self.config_entry.data[CONF_API_KEY]
        )
        self.from_station: StationInfoModel = from_station
        self.to_station: StationInfoModel = to_station
        self._time: time | None = dt_util.parse_time(self.config_entry.data[CONF_TIME])
        self._weekdays: list[str] = self.config_entry.data[CONF_WEEKDAY]
        self._filter_product: str | None = self.config_entry.options.get(
            CONF_FILTER_PRODUCT
        )

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
