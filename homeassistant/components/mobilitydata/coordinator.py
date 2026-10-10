"""Coordinators for the MobilityData integration."""

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import override

from aiomobilitydatabase import (
    EntityType,
    GtfsRtFeed,
    MobilityDatabaseAuthenticationError,
    MobilityDatabaseError,
)
from aiomobilitydatabase.feeds import (
    ArrivalsQuery,
    MobilityFeedsClient,
    MobilityFeedsError,
    SourceAuthenticationError,
    StopArrival,
    TransitFeedHandle,
)

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ARRIVALS_INTERVAL_REALTIME,
    ARRIVALS_INTERVAL_SCHEDULE,
    CONF_FEED_ID,
    CONF_ROUTE_DESTINATIONS,
    CONF_ROUTE_IDS,
    CONF_STOP_IDS,
    CONF_STOP_NAME,
    DEPARTURE_SENSOR_COUNT,
    DOMAIN,
    ISSUE_STOP_MISSING,
    STATIC_REFRESH_INTERVAL,
    STATIC_RETRY_INTERVAL,
    SUBENTRY_TYPE_STOP,
)

_LOGGER = logging.getLogger(__name__)

type MobilityDataConfigEntry = ConfigEntry[MobilityDataRuntimeData]


@dataclass
class MobilityDataRuntimeData:
    """Runtime data for a MobilityData config entry."""

    client: MobilityFeedsClient
    static_coordinator: StaticCoordinator
    arrivals_coordinator: ArrivalsCoordinator


def requires_api_key(rt_feed: GtfsRtFeed) -> bool:
    """Return whether a realtime feed only answers requests carrying a key.

    Catalog authentication types 1 (query parameter) and 2 (header) both
    need the producer's key; 0 is open. Only realtime ever needs one: the
    static schedule comes from the Mobility Database's own hosted copy.
    """
    return (
        rt_feed.source_info is not None
        and rt_feed.source_info.authentication_type in (1, 2)
    )


def board_queries(subentry: ConfigSubentry) -> list[ArrivalsQuery]:
    """Return the queries whose merged results make up one board.

    A board picked as route -> destination pairs needs one query per pair:
    the library filters routes and headsigns as two independent lists, so a
    single query for Blue -> Largo plus Silver -> Ashburn would ALSO match
    Silver -> Largo, a train nobody picked. Each pair is exact on its own,
    and the batched call still costs one realtime fetch.
    """
    stop_ids = subentry.data[CONF_STOP_IDS]
    if pairs := subentry.data[CONF_ROUTE_DESTINATIONS]:
        return [
            ArrivalsQuery(
                stop_ids=stop_ids,
                route_ids=[route_id],
                # A null headsign stands for the route's every departure.
                headsigns=[headsign] if headsign is not None else None,
                limit=DEPARTURE_SENSOR_COUNT,
            )
            for route_id, headsign in pairs
        ]
    return [
        ArrivalsQuery(
            stop_ids=stop_ids,
            route_ids=subentry.data[CONF_ROUTE_IDS] or None,
            limit=DEPARTURE_SENSOR_COUNT,
        )
    ]


def _departs_at(arrival: StopArrival) -> datetime:
    """Order rows the way the library orders a single board."""
    return (
        arrival.predicted_departure
        or arrival.scheduled_departure
        or arrival.predicted_arrival
        or datetime.max.replace(tzinfo=UTC)
    )


def merge_boards(boards: list[list[StopArrival]]) -> list[StopArrival]:
    """Merge one board's per-pair results into its next departures.

    Each per-pair result is already filtered and limited, so the first few
    of their union are exactly the first few of the whole board. A route's
    every-departure pair and one of its specific pairs can both return the
    same trip, hence the de-duplication.
    """
    seen: set[tuple[str | None, str, datetime | None]] = set()
    rows: list[StopArrival] = []
    for arrival in sorted(
        (arrival for board in boards for arrival in board), key=_departs_at
    ):
        key = (arrival.trip_id, arrival.stop_id, arrival.scheduled_departure)
        if key not in seen:
            seen.add(key)
            rows.append(arrival)
    return rows[:DEPARTURE_SENSOR_COUNT]


def stop_subentries(entry: MobilityDataConfigEntry) -> dict[str, ConfigSubentry]:
    """Return the entry's stop subentries keyed by subentry id."""
    return {
        subentry_id: subentry
        for subentry_id, subentry in entry.subentries.items()
        if subentry.subentry_type == SUBENTRY_TYPE_STOP
    }


class StaticCoordinator(DataUpdateCoordinator[TransitFeedHandle]):
    """Own the transit feed handle and its daily static refresh.

    The first refresh acquires the handle (downloading and indexing the GTFS
    dataset if the cache is cold); later refreshes re-check the catalog and
    rebuild only when a new dataset is published. On dataset change, every
    configured stop is re-validated and repair issues raised for stops that
    vanished from the feed.

    Polls on a short retry interval until the first refresh succeeds, then
    settles to the daily one: with no index every entity is unavailable, so
    a transient outage at startup must not cost a full day of data.
    """

    config_entry: MobilityDataConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MobilityDataConfigEntry,
        client: MobilityFeedsClient,
    ) -> None:
        """Initialize the static coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=f"{config_entry.title} static feed",
            update_interval=STATIC_RETRY_INTERVAL,
        )
        self.client = client
        self.stop_ids: set[str] = set()

    @override
    async def _async_update_data(self) -> TransitFeedHandle:
        feed_id: str = self.config_entry.data[CONF_FEED_ID]
        try:
            if self.data is None:
                api_key = self.config_entry.data.get(CONF_API_KEY)
                handle = await self.client.get_transit_feed(feed_id, api_key)
                if api_key is None:
                    # No key was given, so run schedule-only for any producer
                    # that demands one. Left in, the first keyless realtime
                    # request would raise for EVERY board on the entry and
                    # push the user into reauth for a key they chose not to
                    # provide. Keyless realtime siblings are kept.
                    handle.rt_feeds = [
                        rt_feed
                        for rt_feed in handle.rt_feeds
                        if not requires_api_key(rt_feed)
                    ]
            else:
                handle = self.data
                await handle.refresh_static()
        except (MobilityDatabaseAuthenticationError, SourceAuthenticationError) as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except (MobilityDatabaseError, MobilityFeedsError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="static_refresh_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        self.update_interval = STATIC_REFRESH_INTERVAL
        self.stop_ids = {stop.id for stop in handle.stops}
        self._validate_stops()
        return handle

    def _validate_stops(self) -> None:
        """Raise or clear repair issues for stops missing from the dataset."""
        for subentry_id, subentry in stop_subentries(self.config_entry).items():
            issue_id = f"{ISSUE_STOP_MISSING}_{subentry_id}"
            if self.stop_ids.intersection(subentry.data[CONF_STOP_IDS]):
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            else:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key=ISSUE_STOP_MISSING,
                    translation_placeholders={
                        "stop_name": subentry.data[CONF_STOP_NAME],
                        "feed_title": self.config_entry.title,
                    },
                )


class ArrivalsCoordinator(DataUpdateCoordinator[dict[str, list[StopArrival]]]):
    """Fetch upcoming departures for all stop subentries in one batched call.

    Data maps subentry id to that board's arrivals. Each board becomes one
    query per picked route -> destination pair (or one for its routes), all
    sent in a single batched call: the library applies each query's filters
    BEFORE its limit, and the whole batch costs one realtime fetch. Polls
    every minute when the feed family has a usable trip-updates source, else
    every five.
    """

    config_entry: MobilityDataConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MobilityDataConfigEntry,
        static_coordinator: StaticCoordinator,
    ) -> None:
        """Initialize the arrivals coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=f"{config_entry.title} arrivals",
            update_interval=ARRIVALS_INTERVAL_SCHEDULE,
        )
        self.static_coordinator = static_coordinator
        self._interval_resolved = False

    @override
    async def _async_update_data(self) -> dict[str, list[StopArrival]]:
        if (handle := self.static_coordinator.data) is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="static_index_not_ready",
            )
        if not self._interval_resolved:
            self._interval_resolved = True
            if any(
                EntityType.TRIP_UPDATES in (rt_feed.entity_types or [])
                for rt_feed in handle.rt_feeds
            ):
                self.update_interval = ARRIVALS_INTERVAL_REALTIME
        subentries = stop_subentries(self.config_entry)
        if not subentries:
            return {}
        per_board = {
            subentry_id: board_queries(subentry)
            for subentry_id, subentry in subentries.items()
        }
        queries = [query for board in per_board.values() for query in board]
        try:
            results = iter(await handle.get_arrivals(queries))
        except (MobilityDatabaseAuthenticationError, SourceAuthenticationError) as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except (MobilityDatabaseError, MobilityFeedsError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="arrivals_refresh_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return {
            subentry_id: merge_boards([next(results) for _ in board])
            for subentry_id, board in per_board.items()
        }
