"""Common fixtures for the MobilityData tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from aiomobilitydatabase import (
    BoundingBox,
    DataType,
    EntityType,
    FeedStatus,
    GtfsFeed,
    GtfsRtFeed,
    LatestDataset,
    Metadata,
    SearchFeedItemResult,
    SearchResults,
    SourceInfo,
)
from aiomobilitydatabase.feeds import (
    Route,
    StationGroup,
    Stop,
    StopArrival,
    StopLocationType,
)
import pytest

from homeassistant.components.mobilitydata.const import (
    CONF_FEED_ID,
    CONF_HEADSIGNS,
    CONF_REFRESH_TOKEN,
    CONF_ROUTE_IDS,
    CONF_STOP_IDS,
    CONF_STOP_NAME,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

FEED_ID = "mdb-1"
RT_FEED_ID = "mdb-2"
SUBENTRY_ID = "stop_subentry_1"

STOP_1 = Stop(
    id="S1",
    name="1st & Grand",
    latitude=34.05,
    longitude=-118.25,
    parent_station=None,
    location_type=StopLocationType.STOP,
    stop_code=None,
    platform_code=None,
    wheelchair_boarding=None,
    description=None,
    url=None,
    zone_id=None,
    timezone=None,
)
STOP_2 = Stop(
    id="S2",
    name="2nd & Spring",
    latitude=34.06,
    longitude=-118.24,
    parent_station=None,
    location_type=StopLocationType.STOP,
    stop_code=None,
    platform_code=None,
    wheelchair_boarding=None,
    description=None,
    url=None,
    zone_id=None,
    timezone=None,
)
ROUTE_A = Route(
    id="R1",
    short_name="A",
    long_name="Downtown Loop",
    type=3,
    agency_id=None,
    color=None,
    text_color=None,
    url=None,
    description=None,
    sort_order=None,
)
ROUTE_B = Route(
    id="R2",
    short_name="B",
    long_name="Crosstown",
    type=3,
    agency_id=None,
    color=None,
    text_color=None,
    url=None,
    description=None,
    sort_order=None,
)


def make_arrival(
    stop_id: str,
    minute: int,
    *,
    route_id: str = "R1",
    route_name: str = "A Downtown Loop",
    headsign: str = "Downtown",
    realtime: bool = True,
) -> StopArrival:
    """Return a realistic arrival at a fixed, snapshot-stable time."""
    scheduled = datetime(2026, 8, 1, 8, minute, tzinfo=UTC)
    predicted = datetime(2026, 8, 1, 8, minute, 30, tzinfo=UTC) if realtime else None
    return StopArrival(
        stop_id=stop_id,
        stop_name="1st & Grand" if stop_id == "S1" else "2nd & Spring",
        route_id=route_id,
        route_name=route_name,
        trip_id=f"T{minute}",
        headsign=headsign,
        scheduled_arrival=scheduled,
        scheduled_departure=scheduled,
        predicted_arrival=predicted,
        predicted_departure=predicted,
        delay_seconds=30 if realtime else None,
        realtime=realtime,
        vehicle_id=None,
        wheelchair_accessible=None,
        bikes_allowed=None,
        pickup_type=None,
        drop_off_type=None,
        timepoint_exact=True,
        stop_headsign=None,
        trip_short_name=None,
        block_id=None,
    )


ARRIVALS = [
    make_arrival("S1", 5),
    make_arrival(
        "S1",
        12,
        route_id="R2",
        route_name="B Crosstown",
        headsign="Uptown",
        realtime=False,
    ),
    make_arrival("S2", 7),
]

SEARCH_ITEM = SearchFeedItemResult(
    id=FEED_ID,
    data_type=DataType.GTFS,
    status=FeedStatus.ACTIVE,
    provider="LADOT",
)

RT_FEED = GtfsRtFeed(
    id=RT_FEED_ID,
    data_type=DataType.GTFS_RT,
    provider="LADOT",
    entity_types=[EntityType.TRIP_UPDATES],
    feed_references=[FEED_ID],
    source_info=SourceInfo(authentication_type=0),
)
DATASET = LatestDataset(
    id="dataset-1",
    hosted_url="https://example.com/gtfs.zip",
    bounding_box=BoundingBox(
        minimum_latitude=33.9,
        maximum_latitude=34.2,
        minimum_longitude=-118.5,
        maximum_longitude=-118.1,
    ),
)
STATIC_FEED = GtfsFeed(
    id=FEED_ID,
    data_type=DataType.GTFS,
    provider="LADOT",
    latest_dataset=DATASET,
)


@pytest.fixture
def mock_handle() -> MagicMock:
    """Mock a transit feed handle backed by real library models."""
    handle = MagicMock()
    handle.static_feed_id = FEED_ID
    handle.static_dataset = DATASET
    handle.stops = [STOP_1, STOP_2]
    handle.routes = [ROUTE_A, ROUTE_B]
    handle.rt_feeds = [RT_FEED]
    handle.stops_in = MagicMock(return_value=[STOP_1, STOP_2])
    handle.stations_in = MagicMock(
        return_value=[
            StationGroup(id="1st & grand", name="1st & Grand", stop_ids=("S1",)),
            StationGroup(id="2nd & spring", name="2nd & Spring", stop_ids=("S2",)),
        ]
    )
    handle.routes_serving = AsyncMock(return_value=[ROUTE_A, ROUTE_B])
    handle.headsigns_serving = AsyncMock(return_value=["Downtown", "Uptown"])
    handle.get_arrivals = AsyncMock(return_value=list(ARRIVALS))
    handle.refresh_static = AsyncMock(return_value=False)
    handle.close = MagicMock()
    return handle


@pytest.fixture
def mock_client(mock_handle: MagicMock) -> MagicMock:
    """Mock a MobilityFeedsClient with a canned catalog."""
    client = MagicMock()
    client.catalog.get_metadata = AsyncMock(return_value=Metadata(version="1.0.0"))
    client.catalog.search_feeds = AsyncMock(
        return_value=SearchResults(total=1, results=[SEARCH_ITEM])
    )
    client.catalog.get_gtfs_feed = AsyncMock(return_value=STATIC_FEED)
    client.catalog.get_gtfs_rt_feed = AsyncMock(return_value=RT_FEED)
    client.catalog.get_gtfs_feed_gtfs_rt_feeds = AsyncMock(return_value=[RT_FEED])
    client.get_transit_feed = AsyncMock(return_value=mock_handle)
    client.purge_cache = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_feeds_client(mock_client: MagicMock) -> Generator[MagicMock]:
    """Patch MobilityFeedsClient at both import sites."""
    with (
        patch(
            "homeassistant.components.mobilitydata.MobilityFeedsClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.mobilitydata.config_flow.MobilityFeedsClient",
            return_value=mock_client,
        ),
    ):
        yield mock_client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry with one configured stop."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="LADOT",
        unique_id=FEED_ID,
        data={CONF_REFRESH_TOKEN: "refresh-token", CONF_FEED_ID: FEED_ID},
        subentries_data=[
            ConfigSubentryDataWithId(
                data={
                    CONF_STOP_IDS: ["S1"],
                    CONF_STOP_NAME: "1st & Grand",
                    CONF_ROUTE_IDS: [],
                    CONF_HEADSIGNS: [],
                },
                subentry_id=SUBENTRY_ID,
                subentry_type=SUBENTRY_TYPE_STOP,
                title="1st & Grand",
                unique_id="1st & grand",
            )
        ],
    )


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the integration and wait for the background first refresh."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
