"""Test the MobilityData coordinators through observable behavior."""

from datetime import timedelta
from unittest.mock import MagicMock

from aiomobilitydatabase import DataType, EntityType, GtfsRtFeed, SourceInfo
from aiomobilitydatabase.feeds import SourceAuthenticationError, SourceConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.mobilitydata.const import (
    ARRIVALS_INTERVAL_SCHEDULE,
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
from homeassistant.config_entries import SOURCE_REAUTH, ConfigSubentryDataWithId
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import conftest
from .conftest import (
    FEED_ID,
    KEYED_RT_FEED,
    RT_FEED,
    RT_FEED_ID,
    STOP_1,
    STOP_2,
    SUBENTRY_ID,
    make_arrival,
    setup_integration,
)

from tests.common import MockConfigEntry, async_fire_time_changed

NEXT_S1 = "sensor.1st_grand_next_departure"
NEXT_S2 = "sensor.2nd_spring_next_departure"

SECOND_STOP_SUBENTRY = ConfigSubentryDataWithId(
    data={
        CONF_STOP_IDS: ["S2"],
        CONF_STOP_NAME: "2nd & Spring",
        CONF_ROUTE_IDS: [],
        CONF_ROUTE_DESTINATIONS: [],
    },
    subentry_id="stop_subentry_2",
    subentry_type=SUBENTRY_TYPE_STOP,
    title="2nd & Spring",
    unique_id="2nd & spring",
)


async def test_arrivals_batched_across_stops(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_handle: MagicMock,
) -> None:
    """Test one get_arrivals call carries one query per configured stop."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="LADOT",
        unique_id=FEED_ID,
        data={"refresh_token": "refresh-token", "feed_id": FEED_ID},
        subentries_data=[
            ConfigSubentryDataWithId(
                data={
                    CONF_STOP_IDS: ["S1"],
                    CONF_STOP_NAME: "1st & Grand",
                    CONF_ROUTE_IDS: [],
                    CONF_ROUTE_DESTINATIONS: [],
                },
                subentry_id=SUBENTRY_ID,
                subentry_type=SUBENTRY_TYPE_STOP,
                title="1st & Grand",
                unique_id="1st & grand",
            ),
            SECOND_STOP_SUBENTRY,
        ],
    )
    await setup_integration(hass, entry)
    mock_handle.get_arrivals.assert_awaited_once()
    (queries,), _ = mock_handle.get_arrivals.await_args
    assert [list(query.stop_ids) for query in queries] == [["S1"], ["S2"]]
    # Asking for more rows than there are sensors would only discard them.
    assert {query.limit for query in queries} == {DEPARTURE_SENSOR_COUNT}
    assert hass.states.get(NEXT_S1).state == "2026-08-01T08:05:30+00:00"
    assert hass.states.get(NEXT_S2).state == "2026-08-01T08:07:30+00:00"


@pytest.mark.parametrize(
    ("entity_types", "first_tick_calls", "second_tick_calls"),
    [
        pytest.param([EntityType.TRIP_UPDATES], 2, 3, id="realtime_60s"),
        pytest.param([EntityType.VEHICLE_POSITIONS], 1, 2, id="schedule_only_300s"),
    ],
)
async def test_polling_interval_matches_capability(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_handle: MagicMock,
    freezer: FrozenDateTimeFactory,
    entity_types: list[EntityType],
    first_tick_calls: int,
    second_tick_calls: int,
) -> None:
    """Test 60s polling with trip updates, 300s without."""
    mock_handle.rt_feeds = [
        GtfsRtFeed(
            id=RT_FEED_ID,
            data_type=DataType.GTFS_RT,
            entity_types=entity_types,
            feed_references=[FEED_ID],
            source_info=SourceInfo(authentication_type=0),
        )
    ]
    await setup_integration(hass, mock_config_entry)
    assert mock_handle.get_arrivals.await_count == 1

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_handle.get_arrivals.await_count == first_tick_calls

    freezer.tick(timedelta(seconds=245))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_handle.get_arrivals.await_count == second_tick_calls


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_route_and_headsign_filters(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_handle: MagicMock,
) -> None:
    """Test subentry filters reduce which arrivals feed the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="LADOT",
        unique_id=FEED_ID,
        data={"refresh_token": "refresh-token", "feed_id": FEED_ID},
        subentries_data=[
            ConfigSubentryDataWithId(
                data={
                    CONF_STOP_IDS: ["S1"],
                    CONF_STOP_NAME: "1st & Grand",
                    CONF_ROUTE_IDS: ["R2"],
                    CONF_ROUTE_DESTINATIONS: [["R2", "Uptown"]],
                },
                subentry_id=SUBENTRY_ID,
                subentry_type=SUBENTRY_TYPE_STOP,
                title="1st & Grand",
                unique_id="1st & grand",
            )
        ],
    )
    await setup_integration(hass, entry)
    state = hass.states.get(NEXT_S1)
    assert state.state == "2026-08-01T08:12:00+00:00"
    assert state.attributes["route_id"] == "R2"
    assert state.attributes["realtime"] is False
    assert hass.states.get("sensor.1st_grand_second_departure").state == "unknown"


async def test_arrivals_failure_marks_unavailable(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_handle: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a realtime fetch failure marks the sensors unavailable."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(NEXT_S1).state != "unavailable"

    mock_handle.get_arrivals.side_effect = SourceConnectionError("producer down")
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(NEXT_S1).state == "unavailable"


async def test_arrivals_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_handle: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a producer auth failure starts a reauth flow."""
    await setup_integration(hass, mock_config_entry)
    mock_handle.get_arrivals.side_effect = SourceAuthenticationError("bad key")
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_vanished_stop_raises_repair_issue(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_handle: MagicMock,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a stop missing from the dataset raises and later clears an issue."""
    mock_handle.stops = [STOP_2]
    await setup_integration(hass, mock_config_entry)
    issue_id = f"{ISSUE_STOP_MISSING}_{SUBENTRY_ID}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None
    assert hass.states.get(NEXT_S1).state == "unavailable"

    mock_handle.stops = [STOP_1, STOP_2]
    mock_handle.get_arrivals.return_value = [make_arrival("S1", 5)]
    freezer.tick(timedelta(hours=24, seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    assert hass.states.get(NEXT_S1).state != "unavailable"


async def test_static_retries_quickly_until_the_first_success(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_handle: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a startup outage costs minutes, not a day.

    With no index every entity is unavailable, so retrying on the daily
    refresh interval would strand the entry until tomorrow.
    """
    mock_feeds_client.get_transit_feed.side_effect = SourceConnectionError("offline")
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(NEXT_S1).state == "unavailable"

    static = mock_config_entry.runtime_data.static_coordinator
    assert static.update_interval == STATIC_RETRY_INTERVAL

    # Well inside the daily interval: the retry only happens on the short one.
    mock_feeds_client.get_transit_feed.side_effect = None
    mock_feeds_client.get_transit_feed.return_value = mock_handle
    freezer.tick(STATIC_RETRY_INTERVAL + timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert static.data is mock_handle
    # Having recovered, it settles to the daily cadence.
    assert static.update_interval == STATIC_REFRESH_INTERVAL

    # The next arrivals poll then finds an index and the sensors fill in.
    freezer.tick(ARRIVALS_INTERVAL_SCHEDULE + timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(NEXT_S1).state == "2026-08-01T08:05:30+00:00"


def _pair_board_entry(pairs: list[list[str | None]]) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="LADOT",
        unique_id=FEED_ID,
        data={"refresh_token": "refresh-token", "feed_id": FEED_ID},
        subentries_data=[
            ConfigSubentryDataWithId(
                data={
                    CONF_STOP_IDS: ["S1"],
                    CONF_STOP_NAME: "1st & Grand",
                    CONF_ROUTE_IDS: [],
                    CONF_ROUTE_DESTINATIONS: pairs,
                },
                subentry_id=SUBENTRY_ID,
                subentry_type=SUBENTRY_TYPE_STOP,
                title="1st & Grand",
                unique_id="1st & grand",
            )
        ],
    )


# A station where both routes reach Downtown, and the soonest train is the
# one nobody picks: R2 -> Downtown at 08:01.
CROSSED = [
    make_arrival("S1", 1, route_id="R2", route_name="B Crosstown", headsign="Downtown"),
    make_arrival("S1", 5, route_id="R1", headsign="Downtown"),
    make_arrival("S1", 9, route_id="R2", route_name="B Crosstown", headsign="Uptown"),
    make_arrival("S1", 14, route_id="R1", headsign="Uptown"),
]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_picked_pairs_do_not_leak_across_routes(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_handle: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test A -> Downtown plus B -> Uptown never shows B -> Downtown.

    As two independent lists that selection becomes routes {A, B} x
    destinations {Downtown, Uptown}, which also matches B -> Downtown -- the
    soonest train here, and one nobody picked. One query per pair keeps it
    exact, and the batch still costs a single call.
    """
    monkeypatch.setattr(conftest, "ARRIVALS", CROSSED)
    await setup_integration(
        hass, _pair_board_entry([["R1", "Downtown"], ["R2", "Uptown"]])
    )
    shown = [
        (state.attributes["route_id"], state.attributes["headsign"])
        for entity_id in (
            NEXT_S1,
            "sensor.1st_grand_second_departure",
        )
        if (state := hass.states.get(entity_id))
    ]
    assert shown == [("R1", "Downtown"), ("R2", "Uptown")]
    [queries] = mock_handle.get_arrivals.await_args.args
    assert [(q.route_ids, q.headsigns) for q in queries] == [
        (["R1"], ["Downtown"]),
        (["R2"], ["Uptown"]),
    ]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_route_pair_without_destination_is_every_departure(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_handle: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a [route, null] pair is that route's every departure.

    It is how a route the feed gives no destinations for joins a board, and
    overlapping it with a specific pair of the same route must not show the
    shared trip twice.
    """
    monkeypatch.setattr(conftest, "ARRIVALS", CROSSED)
    await setup_integration(hass, _pair_board_entry([["R1", None], ["R1", "Uptown"]]))
    trips = [
        hass.states.get(entity_id).attributes["trip_id"]
        for entity_id in (
            NEXT_S1,
            "sensor.1st_grand_second_departure",
            "sensor.1st_grand_third_departure",
        )
        if hass.states.get(entity_id).state != "unknown"
    ]
    # Every R1 trip once each, in order -- T14 came back from BOTH queries.
    assert trips == ["T5", "T14"]


@pytest.mark.parametrize(
    ("api_key", "kept"),
    [
        pytest.param(None, [RT_FEED], id="no-key-drops-the-keyed-feed"),
        pytest.param("producer-key", [RT_FEED, KEYED_RT_FEED], id="key-keeps-both"),
    ],
)
async def test_without_a_key_keyed_realtime_is_dropped(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_handle: MagicMock,
    api_key: str | None,
    kept: list,
) -> None:
    """Test an entry without a key runs schedule-only for keyed producers.

    Left in, the first keyless request to a keyed producer would raise for
    every board on the entry and push the user into reauth for a key they
    chose not to give. A sibling realtime feed needing no key is kept.
    """
    mock_handle.rt_feeds = [RT_FEED, KEYED_RT_FEED]
    if api_key is not None:
        mock_config_entry.add_to_hass(hass)
        hass.config_entries.async_update_entry(
            mock_config_entry, data={**mock_config_entry.data, "api_key": api_key}
        )
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    else:
        await setup_integration(hass, mock_config_entry)
    assert mock_handle.rt_feeds == kept
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
