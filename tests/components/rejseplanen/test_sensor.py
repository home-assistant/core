"""Test Rejseplanen sensors."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import zoneinfo

from py_rejseplan.dataclasses.departure import DepartureType
import pytest

from homeassistant.components import rejseplanen
from homeassistant.components.rejseplanen.const import DOMAIN
from homeassistant.components.rejseplanen.sensor import (
    _calculate_due_in,
    _get_current_departures,
    _get_departure_attributes,
    _get_departure_timestamp,
    _get_departures_list_attributes,
    _get_next_departure_cleanup_time,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_sensors_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor unique IDs."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Main integration without subentries creates no entities
    assert len(entity_entries) == 0


@pytest.mark.usefixtures("init_integration")
async def test_service_device_created(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test service integration creates a device."""
    # Service integrations create a main device entry
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    # Should have exactly one device for the service
    assert len(device_entries) == 1

    device = device_entries[0]
    assert device.name == "Rejseplanen"
    assert device.manufacturer == "Rejseplanen"
    assert device.entry_type is dr.DeviceEntryType.SERVICE


@pytest.mark.usefixtures("init_integration")
async def test_no_entities_without_subentries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test main integration creates no entities without stop subentries."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # Main integration should not create entities - only subentries do
    assert len(entity_entries) == 0


@pytest.mark.usefixtures("setup_integration_with_stop")
async def test_sensor_created_with_subentry(
    hass: HomeAssistant,
    setup_integration_with_stop: tuple[MockConfigEntry, ConfigSubentry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that sensors are created when a subentry is added."""
    _main_entry, subentry = setup_integration_with_stop

    # Verify entities are created
    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{subentry.subentry_id}_next_departure"
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

    result = _get_departure_attributes([departure], 0)

    assert result["stop_id"] == 123456
    assert result["stop"] == "Test Line"
    assert result["final_stop"] == "Downtown"
    assert result["track"] == "2"
    assert result["cancelled"] is False
    assert result["delay_minutes"] == 0
    assert result["has_realtime"] is False
    assert result["line_type"] == "BUS"
    assert result["operator"] == "Test Operator"

    # Verify timing fields are set
    assert result["planned_time"] is not None
    assert result["realtime_time"] is not None
    assert result["due_in"] is not None
    assert result["due_at"] is not None
    assert result["scheduled_at"] is not None
    assert result["real_time_at"] is not None

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

    result = _get_departure_attributes([rt_departure], 0)

    assert result["stop_id"] == 789012
    assert result["track"] == "3B"  # Should use realtime track
    assert result["has_realtime"] is True
    assert result["delay_minutes"] == 5
    assert result["line_type"] == "TRAIN"
    assert result["operator"] == "Rail Company"

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

    result = _get_departure_attributes([cancelled_departure], 0)

    assert result["cancelled"] is True
    assert result["stop_id"] == 111222

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
    # No product attribute
    delattr(no_product_departure, "product") if hasattr(
        no_product_departure, "product"
    ) else None

    result = _get_departure_attributes([no_product_departure], 0)

    assert result["operator"] is None


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

    assert "departures" in result
    assert len(result["departures"]) == 1
    assert result["total_departures"] == 1
    assert result["next_departure_in"] is not None

    departure_info = result["departures"][0]
    assert departure_info["index"] == 0
    assert departure_info["line"] == "Line 5A"
    assert departure_info["direction"] == "North Station"
    assert departure_info["track"] == "4"
    assert departure_info["is_cancelled"] is False
    assert departure_info["is_delayed"] is False
    assert departure_info["delay_minutes"] == 0
    assert departure_info["delay_text"] is None
    assert departure_info["status_icon"] == "🟢"
    assert departure_info["line_type"] == "BUS"
    assert "due_in" in departure_info
    assert "due_in_text" in departure_info
    assert "scheduled_time" in departure_info
    assert "realtime_time" in departure_info

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

    departure_info = result["departures"][0]
    assert departure_info["is_delayed"] is True
    assert departure_info["delay_minutes"] == 5
    assert departure_info["delay_text"] == "+5 min"
    assert departure_info["status_icon"] == "🔴"
    assert departure_info["track"] == "2B"  # Should use realtime track

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

    assert len(result["departures"]) == 2
    assert result["total_departures"] == 2
    assert result["departures"][0]["index"] == 0
    assert result["departures"][0]["line"] == "Line 1"
    assert result["departures"][1]["index"] == 1
    assert result["departures"][1]["line"] == "Line 2"
    assert result["next_departure_in"] == result["departures"][0]["due_in"]

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

    departure_info = result["departures"][0]
    assert departure_info["is_cancelled"] is True


async def test_yaml_configuration_creates_repair_issue(hass: HomeAssistant) -> None:
    """Test that YAML configuration creates a repair issue."""
    # Set up with YAML configuration
    config = {DOMAIN: {"api_key": "test_key"}}

    result = await rejseplanen.async_setup(hass, config)
    assert result is True

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
