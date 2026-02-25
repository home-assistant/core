"""Test the Teslemetry calendar platform."""

from collections.abc import Generator
from copy import deepcopy
from datetime import datetime
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.calendar import (
    DOMAIN as CALENDAR_DOMAIN,
    EVENT_END_DATETIME,
    EVENT_START_DATETIME,
    SERVICE_GET_EVENTS,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import assert_entities, setup_platform
from .const import SITE_INFO, SITE_INFO_MULTI_SEASON, SITE_INFO_WEEK_CROSSING

ENTITY_BUY = "calendar.energy_site_buy_tariff"
ENTITY_SELL = "calendar.energy_site_sell_tariff"


@pytest.fixture
def mock_site_info_week_crossing(mock_site_info) -> Generator[AsyncMock]:
    """Mock Teslemetry Energy site_info with week-crossing tariff data."""
    with patch(
        "tesla_fleet_api.tesla.energysite.EnergySite.site_info",
        side_effect=lambda: deepcopy(SITE_INFO_WEEK_CROSSING),
    ) as mock:
        yield mock


@pytest.fixture
def mock_site_info_multi_season(mock_site_info) -> Generator[AsyncMock]:
    """Mock Teslemetry Energy site_info with multi-season tariff data."""
    with patch(
        "tesla_fleet_api.tesla.energysite.EnergySite.site_info",
        side_effect=lambda: deepcopy(SITE_INFO_MULTI_SEASON),
    ) as mock:
        yield mock


@pytest.fixture
def mock_site_info_no_tariff(mock_site_info) -> Generator[AsyncMock]:
    """Mock Teslemetry Energy site_info with no tariff data."""
    site_info_no_tariff = deepcopy(SITE_INFO_WEEK_CROSSING)
    site_info_no_tariff["response"]["tariff_content_v2"]["seasons"] = {}
    site_info_no_tariff["response"]["tariff_content_v2"]["sell_tariff"]["seasons"] = {}
    with patch(
        "tesla_fleet_api.tesla.energysite.EnergySite.site_info",
        side_effect=lambda: deepcopy(site_info_no_tariff),
    ) as mock:
        yield mock


@pytest.fixture
def mock_site_info_invalid_season(mock_site_info) -> Generator[AsyncMock]:
    """Mock site_info with invalid/empty season data."""
    site_info = deepcopy(SITE_INFO)
    # Empty season first (hits _get_current_season empty check),
    # then season with missing keys (hits KeyError exception handler)
    site_info["response"]["tariff_content_v2"]["seasons"] = {
        "Empty": {},
        "Invalid": {"someKey": "value"},
    }
    site_info["response"]["tariff_content_v2"]["sell_tariff"]["seasons"] = {}
    with patch(
        "tesla_fleet_api.tesla.energysite.EnergySite.site_info",
        side_effect=lambda: deepcopy(site_info),
    ) as mock:
        yield mock


@pytest.fixture
def mock_site_info_invalid_price(mock_site_info) -> Generator[AsyncMock]:
    """Mock site_info with non-numeric price data."""
    site_info = deepcopy(SITE_INFO)
    site_info["response"]["tariff_content_v2"]["energy_charges"]["Summer"]["rates"] = {
        "OFF_PEAK": "not_a_number",
        "ON_PEAK": "not_a_number",
    }
    site_info["response"]["tariff_content_v2"]["sell_tariff"]["seasons"] = {}
    with patch(
        "tesla_fleet_api.tesla.energysite.EnergySite.site_info",
        side_effect=lambda: deepcopy(site_info),
    ) as mock:
        yield mock


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calendar(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the calendar entity is correct."""
    tz = dt_util.get_default_time_zone()
    freezer.move_to(datetime(2024, 1, 1, 10, 0, 0, tzinfo=tz))

    entry = await setup_platform(hass, [Platform.CALENDAR])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.parametrize(
    "entity_id",
    [ENTITY_BUY, ENTITY_SELL],
)
@pytest.mark.parametrize(
    "time_tuple",
    [
        (2024, 1, 1, 10, 0, 0),  # OFF_PEAK period started yesterday
        (2024, 1, 1, 20, 0, 0),  # ON_PEAK period starts and ends today
        (2024, 1, 1, 22, 0, 0),  # OFF_PEAK period ends tomorrow
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calendar_events(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
    entity_id: str,
    time_tuple: tuple,
) -> None:
    """Tests that the energy tariff calendar entity events are correct."""
    tz = dt_util.get_default_time_zone()
    freezer.move_to(datetime(*time_tuple, tzinfo=tz))

    await setup_platform(hass, [Platform.CALENDAR])

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes == snapshot(name="event")

    result = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: [entity_id],
            EVENT_START_DATETIME: dt_util.parse_datetime("2024-01-01T00:00:00Z"),
            EVENT_END_DATETIME: dt_util.parse_datetime("2024-01-07T00:00:00Z"),
        },
        blocking=True,
        return_response=True,
    )
    assert result == snapshot(name="events")


@pytest.mark.parametrize(
    ("time_tuple", "expected_state", "expected_period"),
    [
        # Friday (day 4) - WEEKEND period active (Fri-Mon crossing)
        ((2024, 1, 5, 12, 0, 0), "on", "Weekend"),
        # Saturday (day 5) - WEEKEND period active
        ((2024, 1, 6, 12, 0, 0), "on", "Weekend"),
        # Sunday (day 6) - WEEKEND period active
        ((2024, 1, 7, 12, 0, 0), "on", "Weekend"),
        # Monday (day 0) - WEEKEND period active (end of Fri-Mon range)
        ((2024, 1, 8, 12, 0, 0), "on", "Weekend"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calendar_week_crossing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
    mock_site_info_week_crossing: AsyncMock,
    time_tuple: tuple,
    expected_state: str,
    expected_period: str,
) -> None:
    """Test calendar handles week-crossing day ranges correctly."""
    tz = dt_util.get_default_time_zone()
    time = datetime(*time_tuple, tzinfo=tz)
    freezer.move_to(time)

    await setup_platform(hass, [Platform.CALENDAR])

    state = hass.states.get(ENTITY_BUY)
    assert state
    assert state.state == expected_state
    assert expected_period in state.attributes["message"]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calendar_week_crossing_excluded_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
    mock_site_info_week_crossing: AsyncMock,
) -> None:
    """Test calendar excludes days outside week-crossing range."""
    tz = dt_util.get_default_time_zone()
    # Wednesday (day 2) - No period active (outside Fri-Mon range)
    freezer.move_to(datetime(2024, 1, 3, 12, 0, 0, tzinfo=tz))

    await setup_platform(hass, [Platform.CALENDAR])

    state = hass.states.get(ENTITY_BUY)
    assert state
    assert state.state == "off"


@pytest.mark.parametrize(
    ("time_tuple", "expected_season", "expected_buy_price"),
    [
        # June 15 at noon - Summer OFF_PEAK (Apr-Sep)
        ((2024, 6, 15, 12, 0, 0), "Summer", "0.20"),
        # July 1 at 18:00 - Summer PEAK
        ((2024, 7, 1, 18, 0, 0), "Summer", "0.35"),
        # December 15 at noon - Winter OFF_PEAK (Oct-Mar, crosses year boundary)
        ((2024, 12, 15, 12, 0, 0), "Winter", "0.12"),
        # January 15 at noon - Winter OFF_PEAK (crosses year boundary)
        ((2024, 1, 15, 12, 0, 0), "Winter", "0.12"),
        # February 28 at 18:00 - Winter PEAK
        ((2024, 2, 28, 18, 0, 0), "Winter", "0.25"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calendar_multi_season(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
    mock_site_info_multi_season: AsyncMock,
    time_tuple: tuple,
    expected_season: str,
    expected_buy_price: str,
) -> None:
    """Test calendar handles multiple seasons and year boundaries correctly."""
    tz = dt_util.get_default_time_zone()
    time = datetime(*time_tuple, tzinfo=tz)
    freezer.move_to(time)

    await setup_platform(hass, [Platform.CALENDAR])

    state = hass.states.get(ENTITY_BUY)
    assert state
    assert state.state == "on"
    assert expected_season in state.attributes["description"]
    assert expected_buy_price in state.attributes["message"]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calendar_no_tariff_data(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
    mock_site_info_no_tariff: AsyncMock,
) -> None:
    """Test calendar entity is not created when tariff data is missing."""
    tz = dt_util.get_default_time_zone()
    freezer.move_to(datetime(2024, 1, 1, 10, 0, 0, tzinfo=tz))

    await setup_platform(hass, [Platform.CALENDAR])

    state = hass.states.get(ENTITY_BUY)
    assert state is None
    state = hass.states.get(ENTITY_SELL)
    assert state is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calendar_invalid_season_data(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
    mock_site_info_invalid_season: AsyncMock,
) -> None:
    """Test calendar handles invalid/empty season data gracefully."""
    tz = dt_util.get_default_time_zone()
    freezer.move_to(datetime(2024, 6, 15, 12, 0, 0, tzinfo=tz))

    await setup_platform(hass, [Platform.CALENDAR])

    # No valid season found -> event returns None -> state is "off"
    state = hass.states.get(ENTITY_BUY)
    assert state
    assert state.state == "off"

    # async_get_events also returns empty when no valid seasons
    result = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: [ENTITY_BUY],
            EVENT_START_DATETIME: dt_util.parse_datetime("2024-06-15T00:00:00Z"),
            EVENT_END_DATETIME: dt_util.parse_datetime("2024-06-17T00:00:00Z"),
        },
        blocking=True,
        return_response=True,
    )
    assert result[ENTITY_BUY]["events"] == []


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calendar_week_crossing_get_events(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
    mock_site_info_week_crossing: AsyncMock,
) -> None:
    """Test async_get_events filters by day of week with week-crossing periods."""
    tz = dt_util.get_default_time_zone()
    freezer.move_to(datetime(2024, 1, 1, 12, 0, 0, tzinfo=tz))

    await setup_platform(hass, [Platform.CALENDAR])

    # Request events for a full week - only Fri-Mon should have events
    result = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: [ENTITY_BUY],
            EVENT_START_DATETIME: dt_util.parse_datetime("2024-01-01T00:00:00Z"),
            EVENT_END_DATETIME: dt_util.parse_datetime("2024-01-08T00:00:00Z"),
        },
        blocking=True,
        return_response=True,
    )
    events = result[ENTITY_BUY]["events"]
    # 5 events: Sun Dec 31, Mon Jan 1, Fri Jan 5, Sat Jan 6, Sun Jan 7
    # (Dec 31 included due to UTC-to-local shift) - no Tue/Wed/Thu
    assert len(events) == 5
    for event in events:
        start = dt_util.parse_datetime(event["start"])
        assert start is not None
        assert start.weekday() in (0, 4, 5, 6)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calendar_midnight_crossing_local_start(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
) -> None:
    """Test async_get_events includes overnight period when query starts at local midnight."""
    tz = dt_util.get_default_time_zone()
    freezer.move_to(datetime(2024, 1, 1, 10, 0, 0, tzinfo=tz))

    await setup_platform(hass, [Platform.CALENDAR])

    # Use local-timezone timestamps so UTC-to-local shift does not
    # accidentally push the start back to the previous day.
    start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=tz)
    end = datetime(2024, 1, 2, 0, 0, 0, tzinfo=tz)

    result = await hass.services.async_call(
        CALENDAR_DOMAIN,
        SERVICE_GET_EVENTS,
        {
            ATTR_ENTITY_ID: [ENTITY_BUY],
            EVENT_START_DATETIME: start,
            EVENT_END_DATETIME: end,
        },
        blocking=True,
        return_response=True,
    )
    events = result[ENTITY_BUY]["events"]

    # Expect 2 events on Jan 1:
    # 1) OFF_PEAK that started Dec 31 21:00 and ends Jan 1 16:00
    # 2) ON_PEAK from Jan 1 16:00 to Jan 1 21:00
    # The OFF_PEAK starting Jan 1 21:00 (ending Jan 2 16:00) also overlaps,
    # so 3 events total.
    assert len(events) == 3

    starts = [dt_util.parse_datetime(e["start"]) for e in events]
    assert starts[0].day == 31  # Dec 31 21:00 (previous evening)
    assert starts[1].day == 1  # Jan 1 16:00
    assert starts[2].day == 1  # Jan 1 21:00


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calendar_invalid_price(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
    mock_site_info_invalid_price: AsyncMock,
) -> None:
    """Test calendar handles non-numeric price data gracefully."""
    tz = dt_util.get_default_time_zone()
    freezer.move_to(datetime(2024, 1, 1, 10, 0, 0, tzinfo=tz))

    await setup_platform(hass, [Platform.CALENDAR])

    # Period matches but price is invalid -> shows "Unknown Price"
    state = hass.states.get(ENTITY_BUY)
    assert state
    assert state.state == "on"
    assert "Unknown Price" in state.attributes["message"]
