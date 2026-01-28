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
from .const import SITE_INFO_MULTI_SEASON, SITE_INFO_WEEK_CROSSING

TZ = dt_util.get_default_time_zone()


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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_calendar(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the calendar entity is correct."""

    TZ = dt_util.get_default_time_zone()
    freezer.move_to(datetime(2024, 1, 1, 10, 0, 0, tzinfo=TZ))

    entry = await setup_platform(hass, [Platform.CALENDAR])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.parametrize(
    ("entity_id"),
    [
        "calendar.energy_site_buy_tariff",
        "calendar.energy_site_sell_tariff",
    ],
)
@pytest.mark.parametrize(
    ("time"),
    [
        datetime(2024, 1, 1, 10, 0, 0, tzinfo=TZ),  # Starts Yesterday
        datetime(2024, 1, 1, 20, 0, 0, tzinfo=TZ),  # Both Today
        datetime(2024, 1, 1, 22, 0, 0, tzinfo=TZ),  # Ends Tomorrow
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
    time: datetime,
) -> None:
    """Tests that the energy tariff calendar entity events are correct."""

    freezer.move_to(time)

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
        # Wednesday (day 2) - No period active (skipped by week-crossing logic)
        ((2024, 1, 3, 12, 0, 0), "off", None),
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
    expected_period: str | None,
) -> None:
    """Test calendar handles week-crossing day ranges correctly."""
    tz = dt_util.get_default_time_zone()
    time = datetime(*time_tuple, tzinfo=tz)
    freezer.move_to(time)

    await setup_platform(hass, [Platform.CALENDAR])

    state = hass.states.get("calendar.energy_site_buy_tariff")
    assert state
    assert state.state == expected_state
    if expected_period:
        assert expected_period in state.attributes["message"]


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

    state = hass.states.get("calendar.energy_site_buy_tariff")
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

    # No calendar entities should be created when seasons are empty
    state = hass.states.get("calendar.energy_site_buy_tariff")
    assert state is None
    state = hass.states.get("calendar.energy_site_sell_tariff")
    assert state is None
