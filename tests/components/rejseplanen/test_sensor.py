"""Test Rejseplanen sensors."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import zoneinfo

from py_rejseplan.dataclasses.departure import DepartureType
import pytest

from homeassistant.components.rejseplanen import sensor as rp_sensor
from homeassistant.components.rejseplanen.const import CONF_STOP_ID, DOMAIN
from homeassistant.components.rejseplanen.sensor import (
    _calculate_due_in,
    _format_departures_for_dashboard,
    _get_current_departures,
    _get_delay_minutes,
    _get_departure_attributes,
    _get_departure_timestamp,
    _get_departures_list_attributes,
    _get_is_delayed,
    _get_next_departure_cleanup_time,
    async_setup_platform,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_integration_with_stop")
async def test_sensor_created_with_subentry(
    hass: HomeAssistant,
    setup_integration_with_stop: tuple[MockConfigEntry, ConfigSubentry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that sensors are created when a subentry is added."""
    _main_entry, subentry = setup_integration_with_stop

    # Verify entities are created (sensor keys use the 'line' sensor)
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{subentry.subentry_id}_line"
    )
    assert entity_id is not None


async def test_integration_loads_successfully(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test integration loads successfully without stops."""
    mock_config_entry.add_to_hass(hass)

    # Mock the API to return empty data (no stops configured)
    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient"
    ) as mock_api_class:
        mock_api = MagicMock()
        mock_api.get_departures.return_value = ([], [])
        mock_api_class.return_value = mock_api

        # Set up the main integration
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Integration should load successfully even without stops
    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Verify no sensor entities were created
    states = hass.states.async_all()
    rejseplanen_entities = [
        state
        for state in states
        if state.entity_id.startswith("sensor.") and "rejseplanen" in state.entity_id
    ]

    # This integration uses subentries, so no sensors should exist without stops configured
    assert len(rejseplanen_entities) == 0, (
        "No entities should exist without stop subentries"
    )


def test_calculate_due_in() -> None:
    """Test the _calculate_due_in helper function."""
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.now(tz)

    # Test departure in 30 minutes
    future_30min = now + timedelta(minutes=30)
    result = _calculate_due_in(future_30min.date(), future_30min.time())
    assert 29 <= result <= 31, f"Expected ~30 minutes, got {result}"

    # Test departure in 1 hour (handles midnight crossing)
    future_1hour = now + timedelta(hours=1)
    result = _calculate_due_in(future_1hour.date(), future_1hour.time())
    assert 59 <= result <= 61, f"Expected ~60 minutes, got {result}"

    # Test departure in the past (should return 0)
    past = now - timedelta(minutes=10)
    result = _calculate_due_in(past.date(), past.time())
    assert result == 0, f"Past departure should return 0, got {result}"

    # Test departure tomorrow (edge case)
    tomorrow = now + timedelta(days=1)
    result = _calculate_due_in(tomorrow.date(), tomorrow.time())
    assert 1439 <= result <= 1441, f"Expected ~1440 minutes (24h), got {result}"


def test_get_current_departures() -> None:
    """Test the _get_current_departures helper function."""
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.now(tz)

    # Test with empty list
    result = _get_current_departures([])
    assert result == []

    # Test with future departures
    future_departure = MagicMock()
    future_time = (now + timedelta(minutes=15)).time()
    future_date = now.date()
    future_departure.time = future_time
    future_departure.date = future_date
    future_departure.rtTime = None
    future_departure.rtDate = None

    result = _get_current_departures([future_departure])
    assert len(result) == 1
    assert result[0] == future_departure

    # Test with past departure (should be filtered out)
    past_departure = MagicMock()
    past_time = (now - timedelta(minutes=10)).time()
    past_date = now.date()
    past_departure.time = past_time
    past_departure.date = past_date
    past_departure.rtTime = None
    past_departure.rtDate = None

    result = _get_current_departures([past_departure])
    assert len(result) == 0

    # Test with mix of past and future departures
    result = _get_current_departures([past_departure, future_departure])
    assert len(result) == 1
    assert result[0] == future_departure

    # Test with realtime data
    rt_departure = MagicMock()
    rt_time = (now + timedelta(minutes=20)).time()
    rt_date = now.date()
    rt_departure.time = (now - timedelta(minutes=5)).time()  # Planned time in past
    rt_departure.date = now.date()
    rt_departure.rtTime = rt_time  # But realtime is in future
    rt_departure.rtDate = rt_date

    result = _get_current_departures([rt_departure])
    assert len(result) == 1
    assert result[0] == rt_departure


def test_get_next_departure_cleanup_time() -> None:
    """Test the _get_next_departure_cleanup_time helper function."""
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.now(tz)

    # Test with empty list - should return None
    result = _get_next_departure_cleanup_time([])
    assert result is None

    # Test with future departure - should return departure time + buffer
    future_departure = MagicMock()
    future_time = (now + timedelta(minutes=30)).time()
    future_date = now.date()
    future_departure.time = future_time
    future_departure.date = future_date
    future_departure.rtTime = None
    future_departure.rtDate = None

    result = _get_next_departure_cleanup_time([future_departure])
    assert result is not None

    # Calculate expected cleanup time (departure + 15 seconds buffer)
    expected_departure_time = datetime.combine(future_date, future_time).replace(
        tzinfo=tz
    )
    expected_cleanup_time = expected_departure_time + timedelta(seconds=15)

    # Allow small tolerance for execution time
    time_diff = abs((result - expected_cleanup_time).total_seconds())
    assert time_diff < 1, (
        f"Expected cleanup time around {expected_cleanup_time}, got {result}"
    )

    # Test with realtime data - should use realtime over planned time
    rt_departure = MagicMock()
    planned_time = (now + timedelta(minutes=10)).time()
    rt_time = (now + timedelta(minutes=15)).time()
    rt_date = now.date()
    rt_departure.time = planned_time
    rt_departure.date = now.date()
    rt_departure.rtTime = rt_time
    rt_departure.rtDate = rt_date

    result = _get_next_departure_cleanup_time([rt_departure])
    assert result is not None

    # Should use realtime, not planned time
    expected_rt_departure = datetime.combine(rt_date, rt_time).replace(tzinfo=tz)
    expected_rt_cleanup = expected_rt_departure + timedelta(seconds=15)

    time_diff = abs((result - expected_rt_cleanup).total_seconds())
    assert time_diff < 1, (
        f"Expected cleanup using realtime {expected_rt_cleanup}, got {result}"
    )

    # Test with multiple departures - should return time for first departure
    first_departure = MagicMock()
    first_time = (now + timedelta(minutes=5)).time()
    first_departure.time = first_time
    first_departure.date = now.date()
    first_departure.rtTime = None
    first_departure.rtDate = None

    second_departure = MagicMock()
    second_time = (now + timedelta(minutes=25)).time()
    second_departure.time = second_time
    second_departure.date = now.date()
    second_departure.rtTime = None
    second_departure.rtDate = None

    result = _get_next_departure_cleanup_time([first_departure, second_departure])
    assert result is not None

    # Should use first departure for cleanup time
    expected_first_departure = datetime.combine(now.date(), first_time).replace(
        tzinfo=tz
    )
    expected_first_cleanup = expected_first_departure + timedelta(seconds=15)

    time_diff = abs((result - expected_first_cleanup).total_seconds())
    assert time_diff < 1, (
        f"Expected cleanup for first departure {expected_first_cleanup}, got {result}"
    )


def test_get_departure_timestamp() -> None:
    """Test the _get_departure_timestamp helper function."""
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.now(tz)

    # Test with empty list - should return None
    result = _get_departure_timestamp([], 0)
    assert result is None

    # Test with index out of bounds - should return None
    departure = MagicMock()
    departure.time = (now + timedelta(minutes=10)).time()
    departure.date = now.date()
    departure.rtTime = None
    departure.rtDate = None

    result = _get_departure_timestamp(
        [departure], 1
    )  # Only 1 item, index 1 is out of bounds
    assert result is None

    # Test with valid departure at index 0 - should return planned timestamp
    planned_time = (now + timedelta(minutes=15)).time()
    planned_date = now.date()
    departure.time = planned_time
    departure.date = planned_date
    departure.rtTime = None
    departure.rtDate = None

    result = _get_departure_timestamp([departure], 0)
    assert result is not None

    expected_timestamp = datetime.combine(planned_date, planned_time).replace(tzinfo=tz)
    time_diff = abs((result - expected_timestamp).total_seconds())
    assert time_diff < 1, f"Expected {expected_timestamp}, got {result}"

    # Test with realtime data - should prefer realtime over planned
    rt_time = (now + timedelta(minutes=20)).time()
    rt_date = now.date()
    departure.time = planned_time  # Planned time
    departure.date = planned_date
    departure.rtTime = rt_time  # Realtime is different
    departure.rtDate = rt_date

    result = _get_departure_timestamp([departure], 0)
    assert result is not None

    expected_rt_timestamp = datetime.combine(rt_date, rt_time).replace(tzinfo=tz)
    time_diff = abs((result - expected_rt_timestamp).total_seconds())
    assert time_diff < 1, f"Expected realtime {expected_rt_timestamp}, got {result}"

    # Test with multiple departures - should return correct index
    first_departure = MagicMock()
    first_time = (now + timedelta(minutes=5)).time()
    first_departure.time = first_time
    first_departure.date = now.date()
    first_departure.rtTime = None
    first_departure.rtDate = None

    second_departure = MagicMock()
    second_time = (now + timedelta(minutes=25)).time()
    second_departure.time = second_time
    second_departure.date = now.date()
    second_departure.rtTime = None
    second_departure.rtDate = None

    # Get first departure (index 0)
    result = _get_departure_timestamp([first_departure, second_departure], 0)
    assert result is not None
    expected_first = datetime.combine(now.date(), first_time).replace(tzinfo=tz)
    time_diff = abs((result - expected_first).total_seconds())
    assert time_diff < 1, f"Expected first departure {expected_first}, got {result}"

    # Get second departure (index 1)
    result = _get_departure_timestamp([first_departure, second_departure], 1)
    assert result is not None
    expected_second = datetime.combine(now.date(), second_time).replace(tzinfo=tz)
    time_diff = abs((result - expected_second).total_seconds())
    assert time_diff < 1, f"Expected second departure {expected_second}, got {result}"

    # Test with past departure - should be filtered out by _get_current_departures
    past_departure = MagicMock()
    past_time = (now - timedelta(minutes=10)).time()
    past_departure.time = past_time
    past_departure.date = now.date()
    past_departure.rtTime = None
    past_departure.rtDate = None

    # If only past departure, should return None (filtered out)
    result = _get_departure_timestamp([past_departure], 0)
    assert result is None


def test_get_departure_attributes() -> None:
    """Test the _get_departure_attributes helper function."""
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.now(tz)

    # Test with empty list - should return empty attributes
    result = _get_departure_attributes([], 0)
    assert result["stop_id"] is None
    assert result["stop"] is None
    assert result["final_stop"] is None
    assert result["track"] is None

    # Test with index out of bounds - should return empty attributes
    departure = MagicMock()
    departure.time = (now + timedelta(minutes=10)).time()
    departure.date = now.date()
    departure.rtTime = None
    departure.rtDate = None

    result = _get_departure_attributes([departure], 1)
    assert result["stop_id"] is None
    assert result["stop"] is None

    # Test with valid departure - basic attributes
    departure = MagicMock()
    departure_time = (now + timedelta(minutes=15)).time()
    departure_date = now.date()
    departure.time = departure_time
    departure.date = departure_date
    departure.rtTime = None
    departure.rtDate = None
    departure.rtTrack = None
    departure.stopExtId = 123456
    departure.name = "Test Line"
    departure.direction = "Downtown"
    departure.track = "2"
    departure.cancelled = False
    departure.type = "BUS"

    # Mock product with operator
    mock_product = MagicMock()
    mock_product.operator = "Test Operator"
    departure.product = mock_product

    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    result = _format_departures_for_dashboard([departure], tz)[0]

    # _format_departures_for_dashboard returns a simplified dictionary used by the
    # dashboard. Assert fields that the formatter actually provides.
    assert result["line"] == "Test Line"
    assert result["direction"] == "Downtown"
    assert result["track"] == "2"
    assert result["is_cancelled"] is False
    assert result["delay_minutes"] == 0
    assert result["line_type"] == "BUS"

    # Verify timing fields are set by the formatter
    assert result["scheduled_time"] is not None
    assert result["realtime_time"] is not None
    assert result["due_in"] is not None
    assert result["due_in_text"] is not None

    # Test with realtime data - should calculate delay
    rt_departure = MagicMock()
    planned_time = (now + timedelta(minutes=20)).time()
    rt_time = (now + timedelta(minutes=25)).time()  # 5 minutes delayed
    rt_departure.time = planned_time
    rt_departure.date = now.date()
    rt_departure.rtTime = rt_time
    rt_departure.rtDate = now.date()
    rt_departure.rtTrack = "3B"
    rt_departure.stopExtId = 789012
    rt_departure.name = "Delayed Line"
    rt_departure.direction = "Airport"
    rt_departure.track = "3A"
    rt_departure.cancelled = False
    rt_departure.type = "TRAIN"

    mock_product = MagicMock()
    mock_product.operator = "Rail Company"
    rt_departure.product = mock_product

    result = _format_departures_for_dashboard([rt_departure], tz)[0]

    assert result["track"] == "3B"  # Should use realtime track
    assert result["is_delayed"] is True
    assert result["delay_minutes"] == 5
    assert result["line_type"] == "TRAIN"

    # Test with cancelled departure
    cancelled_departure = MagicMock()
    cancelled_departure.time = (now + timedelta(minutes=10)).time()
    cancelled_departure.date = now.date()
    cancelled_departure.rtTime = None
    cancelled_departure.rtDate = None
    cancelled_departure.rtTrack = None
    cancelled_departure.stopExtId = 111222
    cancelled_departure.name = "Cancelled Line"
    cancelled_departure.direction = "Suburbs"
    cancelled_departure.track = "1"
    cancelled_departure.cancelled = True
    cancelled_departure.type = "METRO"
    cancelled_departure.product = MagicMock()
    cancelled_departure.product.operator = "Metro Service"

    result = _format_departures_for_dashboard([cancelled_departure], tz)[0]

    assert result["is_cancelled"] is True
    assert result["line"] == "Cancelled Line"

    # Test without product/operator
    no_product_departure = MagicMock()
    no_product_departure.time = (now + timedelta(minutes=10)).time()
    no_product_departure.date = now.date()
    no_product_departure.rtTime = None
    no_product_departure.rtDate = None
    no_product_departure.rtTrack = None
    no_product_departure.stopExtId = 333444
    no_product_departure.name = "Basic Line"
    no_product_departure.direction = "East"
    no_product_departure.track = "5"
    no_product_departure.cancelled = False
    # Simulate missing product/operator by setting product to None
    # Using MagicMock, hasattr() often returns True due to __getattr__ behavior,
    # so explicitly set to None to represent absence of product data.
    no_product_departure.product = None

    result = _format_departures_for_dashboard([no_product_departure], tz)[0]

    # Formatter does not include operator information; ensure it still formats
    # basic fields correctly
    assert result["line"] == "Basic Line"
    assert result["direction"] == "East"


def test_get_departures_list_attributes() -> None:
    """Test the _get_departures_list_attributes helper function."""
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.now(tz)

    # Test with empty list
    result = _get_departures_list_attributes([])
    assert result["departures"] == []
    assert result["last_updated"] is not None

    # Test with single departure
    departure = MagicMock()
    departure_time = (now + timedelta(minutes=10)).time()
    departure.time = departure_time
    departure.date = now.date()
    departure.rtTime = None
    departure.rtDate = None
    departure.rtTrack = None
    departure.name = "Line 5A"
    departure.direction = "North Station"
    departure.track = "4"
    departure.cancelled = False
    departure.type = "BUS"

    result = _get_departures_list_attributes([departure])

    # Current implementation returns total_departures and last_updated for
    # non-empty lists
    assert result["total_departures"] == 1
    assert result["last_updated"] is not None

    # Test with delayed departure
    delayed_departure = MagicMock()
    planned_time = (now + timedelta(minutes=15)).time()
    rt_time = (now + timedelta(minutes=20)).time()  # 5 minutes delayed
    delayed_departure.time = planned_time
    delayed_departure.date = now.date()
    delayed_departure.rtTime = rt_time
    delayed_departure.rtDate = now.date()
    delayed_departure.rtTrack = "2B"
    delayed_departure.name = "Line 10"
    delayed_departure.direction = "Airport"
    delayed_departure.track = "2A"
    delayed_departure.cancelled = False
    delayed_departure.type = "TRAIN"

    result = _get_departures_list_attributes([delayed_departure])

    assert result["total_departures"] == 1
    assert result["last_updated"] is not None

    # Test with multiple departures
    first_departure = MagicMock()
    first_departure.time = (now + timedelta(minutes=5)).time()
    first_departure.date = now.date()
    first_departure.rtTime = None
    first_departure.rtDate = None
    first_departure.rtTrack = None
    first_departure.name = "Line 1"
    first_departure.direction = "West"
    first_departure.track = "1"
    first_departure.cancelled = False
    first_departure.type = "BUS"

    second_departure = MagicMock()
    second_departure.time = (now + timedelta(minutes=12)).time()
    second_departure.date = now.date()
    second_departure.rtTime = None
    second_departure.rtDate = None
    second_departure.rtTrack = None
    second_departure.name = "Line 2"
    second_departure.direction = "East"
    second_departure.track = "2"
    second_departure.cancelled = False
    second_departure.type = "METRO"

    result = _get_departures_list_attributes([first_departure, second_departure])

    assert result["total_departures"] == 2
    assert result["last_updated"] is not None

    # Test with cancelled departure
    cancelled_departure = MagicMock()
    cancelled_departure.time = (now + timedelta(minutes=8)).time()
    cancelled_departure.date = now.date()
    cancelled_departure.rtTime = None
    cancelled_departure.rtDate = None
    cancelled_departure.rtTrack = None
    cancelled_departure.name = "Line 3"
    cancelled_departure.direction = "South"
    cancelled_departure.track = "3"
    cancelled_departure.cancelled = True
    cancelled_departure.type = "BUS"

    result = _get_departures_list_attributes([cancelled_departure])

    assert result["total_departures"] == 1
    assert result["last_updated"] is not None


@pytest.mark.asyncio
async def test_yaml_configuration_creates_repair_issue(hass: HomeAssistant) -> None:
    """Test that YAML configuration creates a repair issue."""
    # Set up with YAML configuration
    config = {DOMAIN: {"api_key": "test_key"}}

    def dummy_add_entities(new_entities, update_before_add: bool = False) -> None:
        """Dummy add entities function."""

    result = await async_setup_platform(hass, config, dummy_add_entities, None)
    assert result is None, "Setup should return None for YAML config"

    # Verify repair issue was created
    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, "yaml_deprecated")

    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_key == "yaml_deprecated"
    assert issue.is_fixable is False


def test_get_current_departures_filters_past() -> None:
    """Test that _get_current_departures filters out past departures."""
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.now(tz)

    # Create departures: one in the past, one in the future
    past_time = now - timedelta(minutes=10)
    future_time = now + timedelta(minutes=30)

    past_departure = MagicMock(spec=DepartureType)
    past_departure.name = "Past Line"
    past_departure.time = past_time.time()
    past_departure.date = past_time.date()
    past_departure.rtTime = None
    past_departure.rtDate = None

    future_departure = MagicMock(spec=DepartureType)
    future_departure.name = "Future Line"
    future_departure.time = future_time.time()
    future_departure.date = future_time.date()
    future_departure.rtTime = None
    future_departure.rtDate = None

    # Test the filtering function
    all_departures = [past_departure, future_departure]
    current_departures = _get_current_departures(all_departures)  # type: ignore[arg-type]

    # Should only include future departure
    assert len(current_departures) == 1
    assert current_departures[0].name == "Future Line"


def test_get_is_delayed() -> None:
    """Test delay detection logic."""
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.now(tz).replace(second=0, microsecond=0)
    future_dt = now + timedelta(minutes=10)

    dep_no_realtime = MagicMock(spec=DepartureType)
    dep_no_realtime.date = future_dt.date()
    dep_no_realtime.time = future_dt.time()
    dep_no_realtime.rtDate = None
    dep_no_realtime.rtTime = None

    result = _get_is_delayed([dep_no_realtime], 0)
    assert result is False, "No realtime data should not indicate delay"

    dep_on_time = MagicMock(spec=DepartureType)
    dep_on_time.date = now.date()
    dep_on_time.time = future_dt.time()
    dep_on_time.rtDate = now.date()
    dep_on_time.rtTime = future_dt.time()

    result = _get_is_delayed([dep_on_time], 0)
    assert result is False, "On-time realtime should not indicate delay"

    dep_delayed = MagicMock(spec=DepartureType)
    dep_delayed.date = future_dt.date()
    dep_delayed.time = future_dt.time()
    dep_delayed.rtDate = future_dt.date()
    dep_delayed.rtTime = (future_dt + timedelta(minutes=5)).time()

    result = _get_is_delayed([dep_delayed], 0)
    assert result is True, "Delayed realtime should indicate delay"

    result = _get_is_delayed([], 0)
    assert result is False, "Empty departures list should not indicate delay"


def test_get_delay_minutes() -> None:
    """Test getter for delay in minutes."""
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    dep_dt = datetime.now(tz).replace(second=0, microsecond=0) + timedelta(minutes=20)

    result = _get_delay_minutes([], 0)
    assert result is None, "No departures should yield None delay"

    dep_on_time = MagicMock(spec=DepartureType)
    dep_on_time.date = dep_dt.date()
    dep_on_time.time = dep_dt.time()
    dep_on_time.rtDate = dep_dt.date()
    dep_on_time.rtTime = dep_dt.time()

    result = _get_delay_minutes([dep_on_time], 0)
    assert result == 0, "On-time departure should yield 0 minutes delay"

    dep_delayed = MagicMock(spec=DepartureType)
    dep_delayed.date = dep_dt.date()
    dep_delayed.time = dep_dt.time()
    dep_delayed.rtDate = dep_dt.date()
    dep_delayed.rtTime = (dep_dt + timedelta(minutes=5)).time()

    result = _get_delay_minutes([dep_delayed], 0)
    assert result == 5, "Delayed departure should yield correct delay"


# Additional tests for delay calculation and cancelled detection
def test_get_departure_attributes_delay_and_cancelled() -> None:
    """Test _get_departure_attributes delay calculation and cancelled detection."""
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.now(tz)

    # Realtime later than planned -> positive delay
    dep = MagicMock(spec=DepartureType)
    dep.date = now.date()
    dep.time = (now + timedelta(minutes=10)).time()
    dep.rtDate = now.date()
    dep.rtTime = (now + timedelta(minutes=15)).time()  # +5 minutes
    dep.rtTrack = None
    dep.stopExtId = 42
    dep.name = "Delay Line"
    dep.direction = "Center"
    dep.track = "1"
    dep.cancelled = False
    dep.type = "BUS"
    dep.product = MagicMock()
    dep.product.operator = "Op"

    attrs = _get_departure_attributes([dep], 0)
    # 5 minute delay expected
    assert attrs["delay_minutes"] == 5
    assert attrs["cancelled"] is False


def test_get_departure_attributes_early_and_cancelled_true() -> None:
    """Test early realtime (negative delay) and cancelled True handling."""
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.now(tz)

    # Realtime earlier than planned -> negative delay (early arrival)
    dep_early = MagicMock(spec=DepartureType)
    dep_early.date = now.date()
    dep_early.time = (now + timedelta(minutes=15)).time()
    dep_early.rtDate = now.date()
    dep_early.rtTime = (now + timedelta(minutes=10)).time()  # -5 minutes
    dep_early.rtTrack = None
    dep_early.stopExtId = 43
    dep_early.name = "Early Line"
    dep_early.direction = "Suburb"
    dep_early.track = "2"
    # Omit 'cancelled' attribute to simulate absence
    dep_early.type = "TRAIN"
    dep_early.product = MagicMock()
    dep_early.product.operator = "Rail"

    attrs_early = _get_departure_attributes([dep_early], 0)
    # Expect a negative value for early arrival (-5)
    assert attrs_early["delay_minutes"] == -5
    # As 'cancelled' attribute is absent, cancelled should be False
    assert attrs_early["cancelled"] is False

    # Now test cancelled True
    dep_cancel = MagicMock(spec=DepartureType)
    dep_cancel.date = now.date()
    dep_cancel.time = (now + timedelta(minutes=10)).time()
    dep_cancel.rtDate = None
    dep_cancel.rtTime = None
    dep_cancel.rtTrack = None
    dep_cancel.stopExtId = 44
    dep_cancel.name = "Cancelled Line"
    dep_cancel.direction = "Nowhere"
    dep_cancel.track = "3"
    dep_cancel.cancelled = True
    dep_cancel.type = "METRO"
    dep_cancel.product = MagicMock()
    dep_cancel.product.operator = "Metro"

    attrs_cancel = _get_departure_attributes([dep_cancel], 0)
    assert attrs_cancel["cancelled"] is True


# @pytest.mark.asyncio
# async def test_sensor_async_setup_entry_calls_add_entities_with_config_subentry_id(
#     hass: HomeAssistant,
# ) -> None:
#     """Directly test sensor.async_setup_entry calls async_add_entities with config_subentry_id."""
#     # Create a MockConfigEntry (duck-typed is fine)
#     entry = MockConfigEntry(domain=DOMAIN, data={})
#     # Make a proper ConfigSubentry for type compatibility
#     subentry_id = "sub_1"
#     subentry = ConfigSubentry(
#         title="Test Stop",
#         unique_id=subentry_id,
#         subentry_id=subentry_id,
#         subentry_type="stop",
#         data=MappingProxyType({CONF_STOP_ID: "123456", CONF_NAME: "Test Stop"}),
#     )
#     entry.subentries = MappingProxyType({subentry_id: subentry})

#     # Provide a minimal runtime_data/coordinator with the things the sensor constructor uses
#     coordinator = MagicMock()
#     # coordinator.api.calculate_departure_type_bitflag is used during sensor init
#     coordinator.api = MagicMock()
#     coordinator.api.calculate_departure_type_bitflag.return_value = 0
#     entry.runtime_data = coordinator

#     called = {}

#     # Fake async_add_entities to capture args — match AddConfigEntryEntitiesCallback signature
#     def fake_add_entities(
#         new_entities,
#         update_before_add: bool = False,
#         *,
#         config_subentry_id: str | None = None,
#     ) -> None:
#         called["entities"] = new_entities
#         called["update_before_add"] = update_before_add
#         called["config_subentry_id"] = config_subentry_id

#     # Call the sensor setup directly
#     await rp_sensor.async_setup_entry(hass, entry, fake_add_entities)

#     assert "entities" in called
#     assert called["config_subentry_id"] == subentry_id
#     # one entity per description in SENSORS
#     assert len(called["entities"]) == len(rp_sensor.SENSORS)


@pytest.mark.asyncio
async def test_schedule_and_cancel_cleanup_and_properties(hass: HomeAssistant) -> None:
    """Test scheduling/canceling cleanup and basic properties on the sensor."""
    tz = zoneinfo.ZoneInfo("Europe/Copenhagen")
    now = datetime.now(tz).replace(second=0, microsecond=0)

    # Create a future departure so cleanup will be scheduled
    future_departure = MagicMock(spec=DepartureType)
    future_departure.date = (now + timedelta(minutes=2)).date()
    future_departure.time = (now + timedelta(minutes=2)).time()
    future_departure.rtTime = None
    future_departure.rtDate = None
    future_departure.stopExtId = 999
    future_departure.name = "Sched Line"
    future_departure.direction = "Center"
    future_departure.track = "1"
    future_departure.cancelled = False
    future_departure.type = "BUS"

    # Coordinator mock
    coordinator = MagicMock()
    coordinator.api = MagicMock()
    coordinator.api.calculate_departure_type_bitflag.return_value = 0
    coordinator.get_filtered_departures.return_value = [future_departure]

    config = {CONF_STOP_ID: "999", "subentry_id": "sub_sched", "name": "Sched Stop"}

    # Instantiate sensor
    description = rp_sensor.SENSORS[0]
    sensor = rp_sensor.RejseplanenTransportSensor(coordinator, config, description)
    # Attach hass for scheduling
    sensor.hass = hass

    # Patch async_write_ha_state to avoid side effects
    sensor.async_write_ha_state = MagicMock()

    # Ensure no unsubscribe yet
    assert sensor._departure_cleanup_unsubscribe is None

    # Schedule cleanup
    sensor._schedule_next_cleanup()

    # After scheduling we should have unsubscribe callable and last_cleanup_time set
    assert sensor._departure_cleanup_unsubscribe is not None
    assert sensor._last_cleanup_time is not None

    # Cancel it and ensure unsubscribe cleared
    sensor._cancel_cleanup_trigger()
    assert sensor._departure_cleanup_unsubscribe is None

    # Test properties: native_value and extra_state_attributes
    # native_value uses value_fn which will attempt to access current departures
    coordinator.get_filtered_departures.return_value = [future_departure]
    val = sensor.native_value
    # For the 'line' description the value is the name of the departure
    assert val == "Sched Line"

    attrs = sensor.extra_state_attributes
    assert attrs["stop_id"] == int(config[CONF_STOP_ID])
    # The departures list attributes should be present via attr_fn when called


def test_list_comprehension_instantiates_all_sensors() -> None:
    """Ensure the list comprehension that creates entities instantiates all sensor types."""
    coordinator = MagicMock()
    coordinator.api = MagicMock()
    coordinator.api.calculate_departure_type_bitflag.return_value = 0

    config = {CONF_STOP_ID: "555", "subentry_id": "sub_comp", "name": "Comp Stop"}

    entities = [
        rp_sensor.RejseplanenTransportSensor(coordinator, config, description)
        for description in rp_sensor.SENSORS
    ]

    assert len(entities) == len(rp_sensor.SENSORS)
