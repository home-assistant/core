"""Coordinators for the MobilityData integration."""

from dataclasses import dataclass
import logging
from typing import override

from aiomobilitydatabase import (
    EntityType,
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
    CONF_HEADSIGNS,
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
                handle = await self.client.get_transit_feed(
                    feed_id, self.config_entry.data.get(CONF_API_KEY)
                )
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

    Data maps subentry id to that board's arrivals. Each subentry becomes one
    ``ArrivalsQuery``, so the library applies that board's route and headsign
    filters BEFORE its limit and the whole batch costs a single realtime
    fetch. Polls every minute when the feed family has a trip-updates capable
    realtime source, else every five.
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
        queries = [
            ArrivalsQuery(
                stop_ids=subentry.data[CONF_STOP_IDS],
                # The flow always writes both, so a missing key is a bug
                # worth surfacing; an empty list means "no narrowing".
                route_ids=subentry.data[CONF_ROUTE_IDS] or None,
                headsigns=subentry.data[CONF_HEADSIGNS] or None,
                limit=DEPARTURE_SENSOR_COUNT,
            )
            for subentry in subentries.values()
        ]
        try:
            boards = await handle.get_arrivals(queries)
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
        return dict(zip(subentries, boards, strict=True))
