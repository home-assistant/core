"""Test the Transport NSW sensor."""

from unittest.mock import Mock, patch

from homeassistant.components.transport_nsw.const import (
    CONF_DESTINATION,
    CONF_ROUTE,
    CONF_STOP_ID,
    DOMAIN,
)
from homeassistant.components.transport_nsw.coordinator import TransportNSWCoordinator
from homeassistant.components.transport_nsw.sensor import TransportNSWSensor
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_CONFIG_DATA = {
    CONF_API_KEY: "test_api_key",
    CONF_STOP_ID: "test_stop_id",
    CONF_NAME: "Test Stop",
    "route": "",
    "destination": "",
}

MOCK_API_RESPONSE = {
    "route": "Test Route",
    "due": 5,
    "delay": 0,
    "real_time": True,
    "destination": "Test Destination",
    "mode": "Bus",
}


async def test_sensor_setup(hass: HomeAssistant) -> None:
    """Test sensor setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.transport_nsw.coordinator.TransportNSW"
    ) as mock_transport:
        mock_transport_instance = mock_transport.return_value
        mock_transport_instance.get_departures.return_value = MOCK_API_RESPONSE

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_stop")
    assert state is not None
    assert state.state == "5"
    assert state.attributes["stop_id"] == "test_stop_id"
    assert state.attributes["route"] == "Test Route"
    assert state.attributes["delay"] == 0
    assert state.attributes["real_time"] is True
    assert state.attributes["destination"] == "Test Destination"
    assert state.attributes["mode"] == "Bus"


async def test_sensor_with_none_values(hass: HomeAssistant) -> None:
    """Test sensor handles API response with None values correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    # Mock API response with None values and n/a values
    mock_response_with_nulls = {
        "route": None,
        "due": "n/a",
        "delay": 0,
        "real_time": True,
        "destination": None,
        "mode": "Bus",
    }

    with patch(
        "homeassistant.components.transport_nsw.coordinator.TransportNSW"
    ) as mock_transport:
        mock_transport_instance = mock_transport.return_value
        mock_transport_instance.get_departures.return_value = mock_response_with_nulls

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.test_stop")
    assert state is not None
    assert state.state == "unknown"  # "n/a" should become None which becomes "unknown"
    assert state.attributes["stop_id"] == "test_stop_id"
    assert state.attributes["route"] is None  # None values should be preserved
    assert state.attributes["delay"] == 0
    assert state.attributes["real_time"] is True
    assert state.attributes["destination"] is None
    assert state.attributes["mode"] == "Bus"


async def test_sensor_with_none_coordinator_data(hass: HomeAssistant) -> None:
    """Test sensor when coordinator data is None."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    # Create a mock coordinator with None data
    mock_coordinator = Mock(spec=TransportNSWCoordinator)
    mock_coordinator.data = None  # Explicitly set data to None

    # Create sensor with mock coordinator that has None data
    sensor = TransportNSWSensor(mock_coordinator, entry, None)

    # Test native_value with None data (line 102)
    assert sensor.native_value is None

    # Test extra_state_attributes with None data (line 109)
    assert sensor.extra_state_attributes is None

    # Test icon with None data (line 129)
    assert sensor.icon == "mdi:clock"  # Default icon from TRANSPORT_ICONS[None]


async def test_sensor_with_data_for_icon_coverage(hass: HomeAssistant) -> None:
    """Test sensor icon handling with various mode values."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    # Test icon with data but None mode (covers line 129)
    mock_coordinator = Mock(spec=TransportNSWCoordinator)
    mock_coordinator.data = {"route": "T1", "mode": None}  # mode is None

    sensor = TransportNSWSensor(mock_coordinator, entry, None)
    assert sensor.icon == "mdi:clock"  # Should fallback to default for None mode


async def test_sensor_with_subentry_mode(hass: HomeAssistant) -> None:
    """Test sensor with subentry data using mock coordinator."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_api_key"},
    )
    entry.add_to_hass(hass)

    # Create a mock subentry
    subentry_data = {
        CONF_STOP_ID: "subentry_stop_id",
        CONF_NAME: "Subentry Stop",
        CONF_ROUTE: "T1",
        CONF_DESTINATION: "Central",
    }

    subentry = ConfigSubentry(
        subentry_id="test_subentry_id",
        subentry_type="stop",
        data=subentry_data,
        title="Test Subentry",
        unique_id="test_unique_id",
    )

    # Create mock coordinator with data
    mock_coordinator = Mock(spec=TransportNSWCoordinator)
    mock_coordinator.data = MOCK_API_RESPONSE

    # Create sensor with subentry
    sensor = TransportNSWSensor(mock_coordinator, entry, subentry)

    # Test that subentry data is used in extra_state_attributes
    attributes = sensor.extra_state_attributes
    assert attributes is not None
    assert attributes["stop_id"] == "subentry_stop_id"  # From subentry.data

    # Test sensor name and unique_id with subentry (now includes route and destination)
    # Name should prioritize custom name from subentry data over title
    assert sensor.name == "Subentry Stop"  # From CONF_NAME in subentry.data
    expected_unique_id = (
        f"{DOMAIN}_{entry.entry_id}_subentry_stop_id_route_T1_dest_Central"
    )
    assert sensor.unique_id == expected_unique_id


async def test_sensor_icon_with_different_modes(hass: HomeAssistant) -> None:
    """Test sensor icon selection for different transport modes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    # Test different transport modes
    test_modes = [
        ("Bus", "mdi:bus"),
        ("Train", "mdi:train"),
        ("Ferry", "mdi:ferry"),
        ("Lightrail", "mdi:tram"),  # Must match const.py mapping
        ("Unknown Mode", "mdi:clock"),  # Fallback to default
        (None, "mdi:clock"),  # None mode should use default
    ]

    for mode, expected_icon in test_modes:
        mock_coordinator = Mock(spec=TransportNSWCoordinator)
        mock_response = MOCK_API_RESPONSE.copy()
        mock_response["mode"] = mode
        mock_coordinator.data = mock_response

        sensor = TransportNSWSensor(mock_coordinator, entry, None)
        assert sensor.icon == expected_icon


async def test_sensor_unique_id_variations(hass: HomeAssistant) -> None:
    """Test sensor unique ID generation with different route/destination combinations."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_api_key"},
    )
    entry.add_to_hass(hass)

    # Test 1: Only stop ID (no route or destination)
    subentry_data_minimal = {
        CONF_STOP_ID: "123456",
    }
    subentry_minimal = ConfigSubentry(
        subentry_id="test_id_1",
        subentry_type="stop",
        data=subentry_data_minimal,
        title="Minimal Stop",
        unique_id="unique_1",
    )

    mock_coordinator = Mock(spec=TransportNSWCoordinator)
    mock_coordinator.data = MOCK_API_RESPONSE
    sensor_minimal = TransportNSWSensor(mock_coordinator, entry, subentry_minimal)
    expected_minimal = f"{DOMAIN}_{entry.entry_id}_123456"
    assert sensor_minimal.unique_id == expected_minimal

    # Test 2: Stop ID + Route only
    subentry_data_route = {
        CONF_STOP_ID: "123456",
        CONF_ROUTE: "T2",
    }
    subentry_route = ConfigSubentry(
        subentry_id="test_id_2",
        subentry_type="stop",
        data=subentry_data_route,
        title="Route Stop",
        unique_id="unique_2",
    )

    sensor_route = TransportNSWSensor(mock_coordinator, entry, subentry_route)
    expected_route = f"{DOMAIN}_{entry.entry_id}_123456_route_T2"
    assert sensor_route.unique_id == expected_route

    # Test 3: Stop ID + Destination only
    subentry_data_dest = {
        CONF_STOP_ID: "123456",
        CONF_DESTINATION: "Parramatta",
    }
    subentry_dest = ConfigSubentry(
        subentry_id="test_id_3",
        subentry_type="stop",
        data=subentry_data_dest,
        title="Destination Stop",
        unique_id="unique_3",
    )

    sensor_dest = TransportNSWSensor(mock_coordinator, entry, subentry_dest)
    expected_dest = f"{DOMAIN}_{entry.entry_id}_123456_dest_Parramatta"
    assert sensor_dest.unique_id == expected_dest

    # Test 4: Empty strings should be ignored
    subentry_data_empty = {
        CONF_STOP_ID: "123456",
        CONF_ROUTE: "",  # Empty string
        CONF_DESTINATION: "   ",  # Whitespace only
    }
    subentry_empty = ConfigSubentry(
        subentry_id="test_id_4",
        subentry_type="stop",
        data=subentry_data_empty,
        title="Empty Values Stop",
        unique_id="unique_4",
    )

    sensor_empty = TransportNSWSensor(mock_coordinator, entry, subentry_empty)
    expected_empty = f"{DOMAIN}_{entry.entry_id}_123456"  # Should be same as minimal
    assert sensor_empty.unique_id == expected_empty


async def test_sensor_dynamic_naming(hass: HomeAssistant) -> None:
    """Test sensor dynamic naming functionality."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_api_key"},
    )
    entry.add_to_hass(hass)

    mock_coordinator = Mock(spec=TransportNSWCoordinator)
    mock_coordinator.data = MOCK_API_RESPONSE

    # Test 1: Custom name in subentry data takes priority
    subentry_data_custom = {
        CONF_STOP_ID: "123456",
        CONF_NAME: "My Custom Stop Name",
        CONF_ROUTE: "T1",
        CONF_DESTINATION: "Central",
    }
    subentry_custom = ConfigSubentry(
        subentry_id="test_id_1",
        subentry_type="stop",
        data=subentry_data_custom,
        title="Ignored Title",
        unique_id="unique_1",
    )

    sensor_custom = TransportNSWSensor(mock_coordinator, entry, subentry_custom)
    assert sensor_custom.name == "My Custom Stop Name"

    # Test 2: Subentry title when no custom name
    subentry_data_title = {
        CONF_STOP_ID: "123456",
        CONF_ROUTE: "T1",
        CONF_DESTINATION: "Central",
    }
    subentry_title = ConfigSubentry(
        subentry_id="test_id_2",
        subentry_type="stop",
        data=subentry_data_title,
        title="Station Name from Title",
        unique_id="unique_2",
    )

    sensor_title = TransportNSWSensor(mock_coordinator, entry, subentry_title)
    assert sensor_title.name == "Station Name from Title"

    # Test 3: Generated name with route and destination
    subentry_data_generated = {
        CONF_STOP_ID: "123456",
        CONF_ROUTE: "T2",
        CONF_DESTINATION: "Parramatta",
    }
    subentry_generated = ConfigSubentry(
        subentry_id="test_id_3",
        subentry_type="stop",
        data=subentry_data_generated,
        title="",  # Empty title
        unique_id="unique_3",
    )

    sensor_generated = TransportNSWSensor(mock_coordinator, entry, subentry_generated)
    assert sensor_generated.name == "Stop 123456 Route T2 to Parramatta"

    # Test 4: Generated name with only route
    subentry_data_route_only = {
        CONF_STOP_ID: "123456",
        CONF_ROUTE: "T3",
    }
    subentry_route_only = ConfigSubentry(
        subentry_id="test_id_4",
        subentry_type="stop",
        data=subentry_data_route_only,
        title=None,  # None title
        unique_id="unique_4",
    )

    sensor_route_only = TransportNSWSensor(mock_coordinator, entry, subentry_route_only)
    assert sensor_route_only.name == "Stop 123456 Route T3"

    # Test 5: Generated name with only destination
    subentry_data_dest_only = {
        CONF_STOP_ID: "123456",
        CONF_DESTINATION: "City",
    }
    subentry_dest_only = ConfigSubentry(
        subentry_id="test_id_5",
        subentry_type="stop",
        data=subentry_data_dest_only,
        title="   ",  # Whitespace only title
        unique_id="unique_5",
    )

    sensor_dest_only = TransportNSWSensor(mock_coordinator, entry, subentry_dest_only)
    assert sensor_dest_only.name == "Stop 123456 to City"

    # Test 6: Minimal name (stop ID only)
    subentry_data_minimal = {
        CONF_STOP_ID: "123456",
    }
    subentry_minimal = ConfigSubentry(
        subentry_id="test_id_6",
        subentry_type="stop",
        data=subentry_data_minimal,
        title="",
        unique_id="unique_6",
    )

    sensor_minimal = TransportNSWSensor(mock_coordinator, entry, subentry_minimal)
    assert sensor_minimal.name == "Stop 123456"

    # Test 7: Empty custom name falls back to title
    subentry_data_empty_name = {
        CONF_STOP_ID: "123456",
        CONF_NAME: "   ",  # Whitespace only
        CONF_ROUTE: "T1",
    }
    subentry_empty_name = ConfigSubentry(
        subentry_id="test_id_7",
        subentry_type="stop",
        data=subentry_data_empty_name,
        title="Fallback Title",
        unique_id="unique_7",
    )

    sensor_empty_name = TransportNSWSensor(mock_coordinator, entry, subentry_empty_name)
    assert sensor_empty_name.name == "Fallback Title"


async def test_sensor_legacy_naming(hass: HomeAssistant) -> None:
    """Test sensor naming in legacy mode."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "test_api_key",
            CONF_STOP_ID: "legacy_stop",
            CONF_NAME: "Legacy Stop Name",
        },
    )
    entry.add_to_hass(hass)

    mock_coordinator = Mock(spec=TransportNSWCoordinator)
    mock_coordinator.data = MOCK_API_RESPONSE

    # Legacy sensor (no subentry)
    sensor_legacy = TransportNSWSensor(mock_coordinator, entry, None)
    assert sensor_legacy.name == "Legacy Stop Name"

    # Test legacy mode with missing name (fallback)
    entry_no_name = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "test_api_key",
            CONF_STOP_ID: "legacy_stop",
        },
    )
    entry_no_name.add_to_hass(hass)

    sensor_no_name = TransportNSWSensor(mock_coordinator, entry_no_name, None)
    assert sensor_no_name.name == "Transport NSW Stop"
