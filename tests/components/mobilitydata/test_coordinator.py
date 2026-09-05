"""Test the MobilityData coordinators through observable behavior."""

from datetime import timedelta
from unittest.mock import MagicMock

from aiomobilitydatabase import DataType, EntityType, GtfsRtFeed, SourceInfo
from aiomobilitydatabase.feeds import SourceAuthenticationError, SourceConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.mobilitydata.const import (
    CONF_HEADSIGNS,
    CONF_ROUTE_IDS,
    CONF_STOP_IDS,
    CONF_STOP_NAME,
    DOMAIN,
    ISSUE_STOP_MISSING,
    SUBENTRY_TYPE_STOP,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigSubentryDataWithId
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .conftest import (
    FEED_ID,
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
        CONF_HEADSIGNS: [],
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
    """Test one get_arrivals call covers every configured stop."""
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
                    CONF_HEADSIGNS: [],
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
    mock_handle.get_arrivals.assert_awaited_once_with(["S1", "S2"])
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
                    CONF_HEADSIGNS: ["Uptown"],
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
