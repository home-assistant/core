"""Test the Transport NSW sensor."""

from unittest.mock import Mock, patch

from homeassistant.components.transport_nsw.const import CONF_STOP_ID, DOMAIN
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
        "route": "T1",
        "destination": "Central",
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

    # Test sensor name and unique_id with subentry
    assert sensor.name == "Test Subentry"
    assert sensor.unique_id == f"{DOMAIN}_{entry.entry_id}_test_subentry_id"


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
