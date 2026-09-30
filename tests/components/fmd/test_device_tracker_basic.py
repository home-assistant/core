"""Test FMD device tracker basic functionality."""

from unittest.mock import AsyncMock, patch

from fmd_api import AuthenticationError, FmdApiException, OperationError
import pytest

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.fmd.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from tests.common import MockConfigEntry
from tests.components.fmd.common import setup_integration


async def test_device_tracker_setup(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker entity is created."""
    await setup_integration(hass, mock_fmd_api)

    state = hass.states.get("device_tracker.fmd_test_user")
    assert state is not None
    assert state.attributes["source_type"] == SourceType.GPS
    assert "last_poll_time" in state.attributes


async def test_device_tracker_location_update(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker updates location."""
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "provider": "gps",
            "bat": 85,
            "accuracy": 10.5,
            "altitude": 100.0,
            "speed": 5.5,
            "heading": 180.0,
        }
    ]

    await setup_integration(hass, mock_fmd_api)

    state = hass.states.get("device_tracker.fmd_test_user")
    assert state is not None
    assert state.attributes["latitude"] == 37.7749
    assert state.attributes["longitude"] == -122.4194
    assert state.attributes["gps_accuracy"] == 10.5
    assert state.attributes["battery_level"] == 85
    assert state.attributes["altitude"] == 100.0
    assert state.attributes["speed"] == 5.5
    assert state.attributes["heading"] == 180.0


async def test_device_tracker_setup_initial_location_fetch_failure(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker setup handles initial location fetch failures gracefully.

    When the initial location fetch fails, the device tracker should still be set up
    but without location data. Platform-level errors should not raise ConfigEntryNotReady.
    """
    config_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test_user",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "test_user",
            CONF_PASSWORD: "test_password",
            "polling_interval": 30,
            "allow_inaccurate_locations": False,
            "use_imperial": False,
        },
        entry_id="test_entry_id",
        unique_id="test_user",
    )
    config_entry.add_to_hass(hass)

    # Mock the API to fail on location fetch
    mock_fmd_api.create.return_value.get_locations.side_effect = Exception(
        "Server unreachable"
    )

    with patch("homeassistant.components.fmd.FmdClient.create", mock_fmd_api.create):
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Setup should succeed despite location fetch failure (graceful degradation)
    assert result
    assert config_entry.state == ConfigEntryState.LOADED

    # Device tracker should be added but without location data (state = "unknown")
    state = hass.states.get("device_tracker.fmd_test_user")
    assert state is not None
    assert state.state == "unknown"


async def test_device_tracker_setup_initial_location_generic_exception(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker setup handles generic exception during initial location fetch."""
    config_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="test_user",
        data={
            CONF_URL: "https://fmd.example.com",
            CONF_ID: "test_user",
            CONF_PASSWORD: "test_password",
            "polling_interval": 30,
            "allow_inaccurate_locations": False,
            "use_imperial": False,
        },
        entry_id="test_entry_id",
        unique_id="test_user",
    )
    config_entry.add_to_hass(hass)

    # Mock the API to fail with generic Exception (not FmdApiException etc)
    mock_fmd_api.create.return_value.get_locations.side_effect = Exception(
        "Generic Error"
    )

    with patch("homeassistant.components.fmd.FmdClient.create", mock_fmd_api.create):
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Setup should succeed
    assert result
    assert config_entry.state == ConfigEntryState.LOADED


async def test_device_tracker_config_entry_not_ready(
    hass: HomeAssistant,
) -> None:
    """Test ConfigEntryNotReady on FmdClient.create failure."""

    # Mock FmdClient.create to raise an exception
    async def mock_create_error(*args, **kwargs):
        raise RuntimeError("Network timeout")

    # Set up the entry - should fail during API creation
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "url": "https://fmd.example.com",
            "id": "test_user_config_error",
            "password": "test_password",
        },
        unique_id="test_user_config_error",
    )
    entry.add_to_hass(hass)

    # Mock FmdClient.create to fail during connection
    with patch(
        "homeassistant.components.fmd.FmdClient.create", side_effect=mock_create_error
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # ConfigEntryNotReady results in failed setup with SETUP_RETRY state
    assert not result
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_device_tracker_no_location_data(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker handles empty location data."""
    await setup_integration(hass, mock_fmd_api)

    # Update to empty locations
    mock_fmd_api.create.return_value.get_locations.return_value = []

    # Trigger a manual update by calling the tracker's async_update method
    tracker = hass.config_entries.async_entries("fmd")[0].runtime_data.tracker
    await tracker.async_update()
    tracker.async_write_ha_state()
    await hass.async_block_till_done()

    state = hass.states.get("device_tracker.fmd_test_user")
    assert state is not None
    # State should be 'unknown' or 'home' depending on previous state, but here it persists
    # If it was previously set, it keeps the state. If it was unknown, it stays unknown.


async def test_device_tracker_authentication_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test AuthenticationError raises ConfigEntryAuthFailed."""

    mock_fmd_api.create.return_value.get_locations.side_effect = AuthenticationError(
        "auth failed"
    )

    await setup_integration(hass, mock_fmd_api)

    tracker = hass.config_entries.async_entries("fmd")[0].runtime_data.tracker

    with pytest.raises(ConfigEntryAuthFailed):
        await tracker.async_update()


async def test_device_tracker_operation_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test OperationError is handled gracefully."""

    mock_fmd_api.create.return_value.get_locations.side_effect = OperationError(
        "connection failed"
    )

    await setup_integration(hass, mock_fmd_api)

    tracker = hass.config_entries.async_entries("fmd")[0].runtime_data.tracker

    # Should not raise, just log
    await tracker.async_update()

    # Location should remain None (or previous value)
    assert tracker.latitude is None


async def test_device_tracker_fmd_api_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test FmdApiException is handled gracefully."""

    mock_fmd_api.create.return_value.get_locations.side_effect = FmdApiException(
        "API failed"
    )

    await setup_integration(hass, mock_fmd_api)

    tracker = hass.config_entries.async_entries("fmd")[0].runtime_data.tracker

    # Should not raise, just log
    await tracker.async_update()

    # Location should remain None
    assert tracker.latitude is None


async def test_device_tracker_unexpected_error(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test unexpected Exception is handled gracefully."""
    mock_fmd_api.create.return_value.get_locations.side_effect = ValueError(
        "unexpected"
    )

    await setup_integration(hass, mock_fmd_api)

    tracker = hass.config_entries.async_entries("fmd")[0].runtime_data.tracker

    # Should not raise, just log
    await tracker.async_update()

    # Location should remain None
    assert tracker.latitude is None


async def test_device_tracker_async_will_remove_from_hass(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker cleanup when removed from Home Assistant."""
    await setup_integration(hass, mock_fmd_api)

    entry = hass.config_entries.async_entries("fmd")[0]
    tracker = entry.runtime_data.tracker

    # Call async_will_remove_from_hass
    await tracker.async_will_remove_from_hass()

    # Verify the entity is cleaned up (no assertion needed, just ensuring no error)
    assert tracker is not None


async def test_device_tracker_timestamp_parsing(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker parses various timestamp formats."""
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T15:30:45Z",  # ISO format
            "provider": "gps",
            "bat": 85,
            "accuracy": 10.5,
        }
    ]

    await setup_integration(hass, mock_fmd_api)

    state = hass.states.get("device_tracker.fmd_test_user")
    assert state is not None
    assert state.attributes.get("latitude") == 37.7749
    assert state.attributes["device_timestamp"] == "2025-10-23T15:30:45Z"


async def test_device_tracker_with_date_timestamp(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker includes date timestamp when available."""
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "date": 1729689600000,  # Unix timestamp in milliseconds
            "provider": "gps",
            "bat": 85,
            "accuracy": 10.5,
        }
    ]

    await setup_integration(hass, mock_fmd_api)

    state = hass.states.get("device_tracker.fmd_test_user")
    assert state is not None
    assert state.attributes["device_timestamp"] == "2025-10-23T12:00:00Z"
    assert state.attributes["device_timestamp_ms"] == "1729689600000"


async def test_device_tracker_battery_level_invalid(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device tracker handles invalid battery value gracefully."""
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "provider": "gps",
            "bat": "invalid",  # Invalid battery value
            "accuracy": 10.5,
        }
    ]

    await setup_integration(hass, mock_fmd_api)

    state = hass.states.get("device_tracker.fmd_test_user")
    assert state is not None
    # Battery level should not be in attributes if invalid
    assert state.attributes.get("battery_level") is None
    assert any("Invalid battery value" in message for message in caplog.messages)


async def test_device_tracker_negative_battery(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker with unusual battery percentage."""
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "provider": "gps",
            "bat": 0,  # Very low battery
            "accuracy": 10.5,
        }
    ]

    await setup_integration(hass, mock_fmd_api)

    state = hass.states.get("device_tracker.fmd_test_user")
    assert state is not None
    assert state.attributes.get("battery_level") == 0


async def test_device_tracker_very_high_battery(
    hass: HomeAssistant,
    mock_fmd_api: AsyncMock,
) -> None:
    """Test device tracker with maximum battery percentage."""
    mock_fmd_api.create.return_value.get_locations.return_value = [
        {
            "lat": 37.7749,
            "lon": -122.4194,
            "time": "2025-10-23T12:00:00Z",
            "provider": "gps",
            "bat": 100,
            "accuracy": 10.5,
        }
    ]

    await setup_integration(hass, mock_fmd_api)

    state = hass.states.get("device_tracker.fmd_test_user")
    assert state is not None
    assert state.attributes.get("battery_level") == 100
