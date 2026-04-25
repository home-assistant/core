"""Data update coordinator for MTA New York City Transit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging

from pymta import BusFeed, MTAFeedError, SubwayFeed

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_LINE,
    CONF_ROUTE,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_BUS,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class MTAArrival:
    """Represents a single transit arrival."""

    arrival_time: datetime
    minutes_until: int
    route_id: str
    destination: str


@dataclass
class MTAData:
    """Data for MTA arrivals."""

    arrivals: list[MTAArrival]


type MTAConfigEntry = ConfigEntry[dict[str, MTADataUpdateCoordinator]]


class MTADataUpdateCoordinator(DataUpdateCoordinator[MTAData]):
    """Class to manage fetching MTA data."""

    config_entry: MTAConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MTAConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize."""
        self.subentry = subentry
        self.stop_id = subentry.data[CONF_STOP_ID]

        session = async_get_clientsession(hass)

        if subentry.subentry_type == SUBENTRY_TYPE_BUS:
            api_key = config_entry.data.get(CONF_API_KEY) or ""
            self.feed: BusFeed | SubwayFeed = BusFeed(api_key=api_key, session=session)
            self.route_id = subentry.data[CONF_ROUTE]
        else:
            # Subway feed
            line = subentry.data[CONF_LINE]
            feed_id = SubwayFeed.get_feed_id_for_route(line)
            self.feed = SubwayFeed(feed_id=feed_id, session=session)
            self.route_id = line

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{subentry.subentry_id}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> MTAData:
        """Fetch data from MTA."""
        _LOGGER.debug(
            "Fetching data for route=%s, stop=%s",
            self.route_id,
            self.stop_id,
        )

        try:
            library_arrivals = await self.feed.get_arrivals(
                route_id=self.route_id,
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
