"""Data update coordinator for MTA New York City Transit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging

from pymta import MTAFeedError, SubwayFeed

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_LINE, CONF_STOP_ID, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class MTAArrival:
    """Represents a single train arrival."""

    arrival_time: datetime
    minutes_until: int
    route_id: str
    destination: str


@dataclass
class MTAData:
    """Data for MTA arrivals."""

    arrivals: list[MTAArrival]


type MTAConfigEntry = ConfigEntry[MTADataUpdateCoordinator]


class MTADataUpdateCoordinator(DataUpdateCoordinator[MTAData]):
    """Class to manage fetching MTA data."""

    config_entry: MTAConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: MTAConfigEntry) -> None:
        """Initialize."""
        self.line = config_entry.data[CONF_LINE]
        self.stop_id = config_entry.data[CONF_STOP_ID]

        self.feed_id = SubwayFeed.get_feed_id_for_route(self.line)
        session = async_get_clientsession(hass)
        self.subway_feed = SubwayFeed(feed_id=self.feed_id, session=session)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> MTAData:
        """Fetch data from MTA."""
        _LOGGER.debug(
            "Fetching data for line=%s, stop=%s, feed=%s",
            self.line,
            self.stop_id,
            self.feed_id,
        )

        try:
            library_arrivals = await self.subway_feed.get_arrivals(
                route_id=self.line,
                stop_id=self.stop_id,
                max_arrivals=3,
            )
        except MTAFeedError as err:
            raise UpdateFailed(f"Error fetching MTA data: {err}") from err

        now = dt_util.now()
        arrivals: list[MTAArrival] = []

        for library_arrival in library_arrivals:
            # Convert UTC arrival time to local time
            arrival_time = dt_util.as_local(library_arrival.arrival_time)

            minutes_until = int((arrival_time - now).total_seconds() / 60)

            _LOGGER.debug(
                "Stop %s: arrival_time=%s, minutes_until=%d, route=%s",
                library_arrival.stop_id,
                arrival_time,
                minutes_until,
                library_arrival.route_id,
            )

            arrivals.append(
                MTAArrival(
                    arrival_time=arrival_time,
                    minutes_until=minutes_until,
                    route_id=library_arrival.route_id,
                    destination=library_arrival.destination,
                )
            )

        _LOGGER.debug("Returning %d arrivals", len(arrivals))

        return MTAData(arrivals=arrivals)
