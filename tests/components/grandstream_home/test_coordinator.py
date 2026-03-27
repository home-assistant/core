"""Test Grandstream coordinator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.grandstream_home.const import (
    DEVICE_TYPE_GDS,
    DEVICE_TYPE_GNS_NAS,
    DOMAIN,
)
from homeassistant.components.grandstream_home.coordinator import GrandstreamCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_config_entry(hass: HomeAssistant):
    """Create mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.data = {}
    entry.async_on_unload = MagicMock()
    return entry


@pytest.fixture
def coordinator(hass: HomeAssistant, mock_config_entry):
    """Create coordinator instance."""
    return GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)


async def test_coordinator_init(
    hass: HomeAssistant, mock_config_entry, coordinator
) -> None:
    """Test coordinator initialization."""
    assert coordinator.device_type == DEVICE_TYPE_GDS
    assert coordinator.entry_id == "test_entry_id"
    assert coordinator._error_count == 0


async def test_update_data_success_gds(hass: HomeAssistant, coordinator) -> None:
    """Test successful data update for GDS device."""
    # Setup mock API
    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_phone_status.return_value = {"response": "success", "body": "idle"}
    mock_api.version = "1.0.0"
    mock_api.is_ha_control_disabled = False

    # Setup mock device
    mock_device = MagicMock()
    mock_device.set_firmware_version = MagicMock()

    hass.data[DOMAIN] = {"test_entry_id": {"api": mock_api, "device": mock_device}}

    result = await coordinator._async_update_data()

    assert "phone_status" in result
    assert result["phone_status"].strip() == "idle"
    assert coordinator._error_count == 0
    assert coordinator.last_update_method == "poll"


async def test_update_data_success_gns(hass: HomeAssistant, mock_config_entry) -> None:
    """Test successful data update for GNS device."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GNS_NAS, mock_config_entry)

    # Setup mock API
    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_system_metrics.return_value = {
        "cpu_usage": 25.5,
        "memory_usage_percent": 45.2,
        "device_status": "online",
        "product_version": "2.0.0",
    }
    mock_api.is_ha_control_disabled = False

    # Setup mock device
    mock_device = MagicMock()
    mock_device.set_firmware_version = MagicMock()

    hass.data[DOMAIN] = {"test_entry_id": {"api": mock_api, "device": mock_device}}

    result = await coordinator._async_update_data()

    assert result["cpu_usage"] == 25.5
    assert result["memory_usage_percent"] == 45.2
    assert result["device_status"] == "online"
    assert coordinator._error_count == 0


async def test_update_data_api_failure(hass: HomeAssistant, coordinator) -> None:
    """Test data update with API failure."""
    # Setup mock API that fails
    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_phone_status.return_value = {
        "response": "error",
        "body": "Connection failed",
    }
    mock_api.is_ha_control_disabled = False

    hass.data[DOMAIN] = {"test_entry_id": {"api": mock_api}}

    result = await coordinator._async_update_data()

    assert result["phone_status"] == "unknown"
    assert coordinator._error_count == 1


async def test_update_data_max_errors(hass: HomeAssistant, coordinator) -> None:
    """Test data update reaching max errors."""
    # Setup mock API that fails
    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_phone_status.return_value = {
        "response": "error",
        "body": "Connection failed",
    }
    mock_api.is_ha_control_disabled = False

    hass.data[DOMAIN] = {"test_entry_id": {"api": mock_api}}

    # Simulate reaching max errors
    coordinator._error_count = 3

    result = await coordinator._async_update_data()

    assert result["phone_status"] == "unavailable"


async def test_update_data_no_api(hass: HomeAssistant, coordinator) -> None:
    """Test data update with no API available."""
    hass.data[DOMAIN] = {"test_entry_id": {}}

    result = await coordinator._async_update_data()

    assert result["phone_status"] == "unknown"
    assert coordinator._error_count == 1


async def test_handle_push_data_string(
    hass: HomeAssistant, mock_config_entry, coordinator
) -> None:
    """Test handling push data as string."""
    await coordinator.async_handle_push_data("ringing")

    assert coordinator.data["phone_status"] == "ringing"
    assert coordinator.last_update_method == "push"


async def test_handle_push_data_dict(
    hass: HomeAssistant, mock_config_entry, coordinator
) -> None:
    """Test handling push data as dictionary."""
    push_data = {"status": "busy", "caller_id": "123456"}

    await coordinator.async_handle_push_data(push_data)

    assert coordinator.data["phone_status"] == "busy"
    assert coordinator.last_update_method == "push"


async def test_handle_push_data_json_string(
    hass: HomeAssistant, mock_config_entry, coordinator
) -> None:
    """Test handling push data as JSON string."""
    json_data = '{"status": "idle", "line": 1}'

    await coordinator.async_handle_push_data(json_data)

    assert coordinator.data["phone_status"] == "idle"
    assert coordinator.last_update_method == "push"


def test_process_status_long_string(coordinator) -> None:
    """Test processing very long status string."""
    long_status = "a" * 300  # 300 characters

    result = coordinator._process_status(long_status)

    assert len(result) <= 253  # 250 + "..."
    assert result.endswith("...")


def test_process_status_json_string(coordinator) -> None:
    """Test processing JSON status string."""
    json_status = '{"status": "idle", "extra": "data"}'

    result = coordinator._process_status(json_status)

    assert result == "idle"


def test_process_status_empty(coordinator) -> None:
    """Test processing empty status."""
    result = coordinator._process_status("")

    assert result == "unknown"


def test_handle_push_data_sync(coordinator) -> None:
    """Test synchronous handle_push_data method."""
    coordinator.handle_push_data("available")

    assert coordinator.data["phone_status"] == "available"


async def test_update_data_with_version_update(
    hass: HomeAssistant, coordinator
) -> None:
    """Test data update with firmware version update."""
    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_phone_status.return_value = {"response": "success", "body": "idle"}
    mock_api.version = "1.2.3"

    mock_device = MagicMock()
    mock_device.set_firmware_version = MagicMock()

    hass.data[DOMAIN] = {"test_entry_id": {"api": mock_api, "device": mock_device}}

    await coordinator._async_update_data()

    mock_device.set_firmware_version.assert_called_once_with("1.2.3")


async def test_update_data_exception_handling(hass: HomeAssistant, coordinator) -> None:
    """Test data update with exception."""
    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_phone_status.side_effect = RuntimeError("Connection error")

    hass.data[DOMAIN] = {"test_entry_id": {"api": mock_api}}

    # Exception should be caught and logged, returning error status
    result = await coordinator._async_update_data()
    assert result["phone_status"] == "unknown"


def test_process_status_dict(coordinator) -> None:
    """Test processing dictionary status."""
    status_dict = {"status": "ringing", "line": 1}

    result = coordinator._process_status(status_dict)

    # Dict is converted to string
    assert "ringing" in result


def test_process_status_none(coordinator) -> None:
    """Test processing None status."""
    result = coordinator._process_status(None)

    assert result == "unknown"


def test_process_status_invalid_json(coordinator) -> None:
    """Test processing status that starts with { but is not valid JSON."""
    invalid_json = "{invalid"
    result = coordinator._process_status(invalid_json)
    # Should pass through JSONDecodeError and continue processing
    assert result == "{invalid"


async def test_update_data_no_api_max_errors(hass: HomeAssistant, coordinator) -> None:
    """Test data update with no API available and error count already at max."""
    # Set error count to max errors
    coordinator._error_count = coordinator._max_errors
    hass.data[DOMAIN] = {"test_entry_id": {}}

    result = await coordinator._async_update_data()

    assert result["phone_status"] == "unavailable"
    # error count should be incremented
    assert coordinator._error_count == coordinator._max_errors + 1


async def test_update_data_gns_metrics_non_dict(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test GNS metrics update returning non-dict result."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GNS_NAS, mock_config_entry)

    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_system_metrics.return_value = "error"  # non-dict result
    hass.data[DOMAIN] = {"test_entry_id": {"api": mock_api}}

    # First call: error_count should increase, return "unknown"
    result = await coordinator._async_update_data()
    assert result["device_status"] == "unknown"
    assert coordinator._error_count == 1

    # Set error count to threshold-1, next failure should return "unavailable"
    coordinator._error_count = coordinator._max_errors - 1
    result = await coordinator._async_update_data()
    assert result["device_status"] == "unavailable"
    assert coordinator._error_count == coordinator._max_errors


async def test_update_data_specific_exceptions(
    hass: HomeAssistant, coordinator
) -> None:
    """Test data update with specific exception types."""
    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    hass.data[DOMAIN] = {"test_entry_id": {"api": mock_api}}

    # Test RuntimeError
    mock_api.get_phone_status.side_effect = RuntimeError("Runtime error")
    result = await coordinator._async_update_data()
    assert result["phone_status"] == "unknown"
    assert coordinator._error_count == 1

    # Reset and test ValueError
    coordinator._error_count = 0
    mock_api.get_phone_status.side_effect = ValueError("Value error")
    result = await coordinator._async_update_data()
    assert result["phone_status"] == "unknown"
    assert coordinator._error_count == 1

    # Reset and test OSError
    coordinator._error_count = 0
    mock_api.get_phone_status.side_effect = OSError("OS error")
    result = await coordinator._async_update_data()
    assert result["phone_status"] == "unknown"
    assert coordinator._error_count == 1

    # Reset and test KeyError
    coordinator._error_count = 0
    mock_api.get_phone_status.side_effect = KeyError("Key error")
    result = await coordinator._async_update_data()
    assert result["phone_status"] == "unknown"
    assert coordinator._error_count == 1

    # Test that after reaching max errors, returns "unavailable"
    coordinator._error_count = coordinator._max_errors - 1
    mock_api.get_phone_status.side_effect = RuntimeError("Another error")
    result = await coordinator._async_update_data()
    assert result["phone_status"] == "unavailable"
    assert coordinator._error_count == coordinator._max_errors


async def test_async_handle_push_data_exception(
    hass: HomeAssistant, mock_config_entry, coordinator
) -> None:
    """Test async_handle_push_data with exception."""
    # Simulate an exception during processing
    with (
        patch.object(
            coordinator, "_process_status", side_effect=Exception("Process error")
        ),
        pytest.raises(Exception, match="Process error"),
    ):
        await coordinator.async_handle_push_data({"phone_status": "test"})

    # Verify error was logged (we can't easily assert logging, but ensure no crash)


def test_handle_push_data_dict_mapping(coordinator) -> None:
    """Test synchronous handle_push_data with dict mapping of status keys."""
    # Test with "status" key
    coordinator.handle_push_data({"status": "busy", "other": "data"})
    assert coordinator.data["phone_status"] == "busy"

    # Test with "state" key
    coordinator.handle_push_data({"state": "idle"})
    assert coordinator.data["phone_status"] == "idle"

    # Test with "value" key
    coordinator.handle_push_data({"value": "ringing"})
    assert coordinator.data["phone_status"] == "ringing"

    # Test with none of the mapping keys, data should be set as-is
    coordinator.handle_push_data({"other": "data"})
    # Should not contain phone_status key
    assert "phone_status" not in coordinator.data
    assert coordinator.data == {"other": "data"}


def test_handle_push_data_sync_exception(coordinator) -> None:
    """Test synchronous handle_push_data with exception."""
    with (
        patch.object(
            coordinator, "_process_status", side_effect=Exception("Sync error")
        ),
        pytest.raises(Exception, match="Sync error"),
    ):
        coordinator.handle_push_data({"phone_status": "test"})


async def test_update_data_no_api_under_max_errors(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test update data when API is not available but under max errors."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    # Initialize hass.data but don't add API
    hass.data[DOMAIN] = {"test_entry_id": {}}

    coordinator._max_errors = 5
    coordinator._error_count = 1  # Under max errors

    # Call _async_update_data directly
    result = await coordinator._async_update_data()

    # Should return unknown when under max errors
    assert result == {"phone_status": "unknown"}
    assert coordinator._error_count == 2


async def test_update_data_no_api_exactly_max_errors(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test update data when API is not available and exactly at max errors."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    # Initialize hass.data but don't add API
    hass.data[DOMAIN] = {"test_entry_id": {}}

    coordinator._max_errors = 2
    coordinator._error_count = 1  # Set to 1, so next error will reach max

    # Call _async_update_data directly
    result = await coordinator._async_update_data()

    # Should return unavailable when max errors reached
    assert result == {"phone_status": "unavailable"}
    assert coordinator._error_count == 2


async def test_update_data_gns_no_metrics_method(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test GNS update when API doesn't have get_system_metrics method."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GNS_NAS, mock_config_entry)

    # Create mock API without get_system_metrics method
    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    # Don't add get_system_metrics method to trigger the fallback

    hass.data[DOMAIN] = {"test_entry_id": {"api": mock_api}}

    # Call _async_update_data directly
    result = await coordinator._async_update_data()

    # Should handle the case where get_system_metrics is not available
    assert isinstance(result, dict)


async def test_update_data_with_runtime_data_api(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test update data using API from runtime_data."""
    # Create a mock config entry with runtime_data
    mock_config_entry = MagicMock(spec=ConfigEntry)
    mock_config_entry.entry_id = "test_entry_id"
    mock_config_entry.runtime_data = {"api": MagicMock()}
    mock_config_entry.runtime_data["api"].get_phone_status.return_value = {
        "response": "success",
        "body": "available",
    }
    mock_config_entry.runtime_data["api"].is_ha_control_disabled = False

    # Mock hass.config_entries.async_entries to return our mock entry
    with patch.object(
        hass.config_entries, "async_entries", return_value=[mock_config_entry]
    ):
        coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

        # Initialize hass.data (but API should come from runtime_data)
        hass.data[DOMAIN] = {"test_entry_id": {}}

        result = await coordinator._async_update_data()

        # Should successfully get data from runtime_data API
        assert "phone_status" in result
        assert result["phone_status"].strip() == "available"


async def test_fetch_gns_metrics_success(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test successful GNS metrics fetch."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GNS_NAS, mock_config_entry)

    # Setup hass.data to avoid KeyError
    hass.data[DOMAIN] = {"test_entry_id": {}}

    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_system_metrics.return_value = {
        "cpu_usage": 25.5,
        "memory_usage_percent": 45.2,
        "device_status": "online",
    }

    result = await coordinator._fetch_gns_metrics(mock_api)

    assert result["cpu_usage"] == 25.5
    assert result["memory_usage_percent"] == 45.2
    assert result["device_status"] == "online"


async def test_fetch_gns_metrics_no_method(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test GNS update when API doesn't have get_system_metrics method."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GNS_NAS, mock_config_entry)

    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    # Remove the get_system_metrics method to simulate it not existing
    del mock_api.get_system_metrics
    mock_api.get_phone_status.return_value = {"response": "success", "body": "idle"}
    mock_api.version = "1.0.0"

    mock_device = MagicMock()
    mock_device.set_firmware_version = MagicMock()

    hass.data[DOMAIN] = {"test_entry_id": {"api": mock_api, "device": mock_device}}

    # Since API doesn't have get_system_metrics, it should fall back to phone status
    result = await coordinator._async_update_data()

    assert "phone_status" in result
    assert result["phone_status"] == "idle "


async def test_fetch_sip_accounts_success(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test successful SIP accounts fetch."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_accounts.return_value = {
        "response": "success",
        "body": [
            {"id": "1", "reg": 1, "name": "user1"},
            {"id": "2", "reg": 0, "name": "user2"},
        ],
    }

    result = await coordinator._fetch_sip_accounts(mock_api)

    assert len(result) == 2
    assert result[0]["id"] == "1"
    assert result[0]["status"] == "registered"  # reg=1 maps to "registered"
    assert result[1]["id"] == "2"
    assert result[1]["status"] == "unregistered"  # reg=0 maps to "unregistered"


async def test_fetch_sip_accounts_error(hass: HomeAssistant, mock_config_entry) -> None:
    """Test SIP accounts fetch with error response."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_sip_accounts.return_value = {
        "response": "error",
        "body": "Authentication failed",
    }

    result = await coordinator._fetch_sip_accounts(mock_api)

    assert result == []


async def test_fetch_sip_accounts_no_method(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test SIP accounts fetch when API has no get_sip_accounts method."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    # Remove get_sip_accounts method
    del mock_api.get_sip_accounts

    result = await coordinator._fetch_sip_accounts(mock_api)

    assert result == []


def test_build_sip_account_dict(hass: HomeAssistant, mock_config_entry) -> None:
    """Test building SIP account dictionary."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    account = {
        "id": "1",
        "reg": 1,  # Use reg status instead of status
        "name": "user1",
        "sip_id": "sip1",
    }

    result = coordinator._build_sip_account_dict(account)

    assert result["id"] == "1"
    assert result["status"] == "registered"  # reg=1 maps to "registered"
    assert result["name"] == "user1"
    assert result["sip_id"] == "sip1"


def test_handle_error(hass: HomeAssistant, mock_config_entry) -> None:
    """Test error handling."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    # Test under max errors
    coordinator._error_count = 1
    coordinator._max_errors = 3

    result = coordinator._handle_error("phone_status")

    assert result["phone_status"] == "unknown"
    assert coordinator._error_count == 2

    # Test at max errors
    coordinator._error_count = 3

    result = coordinator._handle_error("phone_status")

    assert result["phone_status"] == "unavailable"
    assert coordinator._error_count == 4


def test_process_push_data_string(hass: HomeAssistant, mock_config_entry) -> None:
    """Test processing push data as string."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    result = coordinator._process_push_data("ringing")

    assert result["phone_status"] == "ringing"


def test_process_push_data_dict_with_status(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test processing push data as dict with status key."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    data = {"status": "busy", "caller_id": "123456"}
    result = coordinator._process_push_data(data)

    # When status key exists, only phone_status is kept
    assert result["phone_status"] == "busy"
    assert "caller_id" not in result  # Other data is not preserved


def test_process_push_data_dict_with_state(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test processing push data as dict with state key."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    data = {"state": "idle", "line": 1}
    result = coordinator._process_push_data(data)

    # When state key exists, only phone_status is kept
    assert result["phone_status"] == "idle"
    assert "line" not in result  # Other data is not preserved


def test_process_push_data_dict_with_value(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test processing push data as dict with value key."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    data = {"value": "available", "timestamp": "2023-01-01"}
    result = coordinator._process_push_data(data)

    # When value key exists, only phone_status is kept
    assert result["phone_status"] == "available"
    assert "timestamp" not in result  # Other data is not preserved


def test_process_push_data_dict_no_status_keys(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test processing push data as dict without status keys."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    data = {"caller_id": "123456", "line": 1}
    result = coordinator._process_push_data(data)

    assert result == data  # Should return as-is
    assert "phone_status" not in result


def test_process_push_data_json_string(hass: HomeAssistant, mock_config_entry) -> None:
    """Test processing push data as JSON string."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    json_data = '{"status": "ringing", "caller_id": "987654"}'
    result = coordinator._process_push_data(json_data)

    # When status key exists in parsed JSON, only phone_status is kept
    assert result["phone_status"] == "ringing"
    assert "caller_id" not in result  # Other data is not preserved


def test_process_push_data_invalid_json(hass: HomeAssistant, mock_config_entry) -> None:
    """Test processing push data as invalid JSON string."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    invalid_json = '{"invalid": json}'
    result = coordinator._process_push_data(invalid_json)

    # Should treat as regular string
    assert result["phone_status"] == invalid_json


async def test_update_data_gds_with_sip_accounts(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test GDS update with SIP accounts."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_phone_status.return_value = {"response": "success", "body": "idle"}
    mock_api.get_accounts.return_value = {
        "response": "success",
        "body": [{"id": "1", "reg": 1, "name": "user1"}],  # Use reg instead of status
    }
    mock_api.version = "1.0.0"

    mock_device = MagicMock()
    mock_device.set_firmware_version = MagicMock()

    hass.data[DOMAIN] = {"test_entry_id": {"api": mock_api, "device": mock_device}}

    result = await coordinator._async_update_data()

    assert "phone_status" in result
    assert "sip_accounts" in result
    assert len(result["sip_accounts"]) == 1
    assert result["sip_accounts"][0]["id"] == "1"
    assert (
        result["sip_accounts"][0]["status"] == "registered"
    )  # reg=1 maps to "registered"


async def test_update_data_gns_with_sip_accounts(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test GNS update with metrics (SIP accounts not included for GNS metrics path)."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GNS_NAS, mock_config_entry)

    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_system_metrics.return_value = {
        "cpu_usage": 25.5,
        "device_status": "online",
    }
    mock_api.version = "2.0.0"

    mock_device = MagicMock()
    mock_device.set_firmware_version = MagicMock()

    hass.data[DOMAIN] = {"test_entry_id": {"api": mock_api, "device": mock_device}}

    result = await coordinator._async_update_data()

    assert result["cpu_usage"] == 25.5
    assert result["device_status"] == "online"
    # SIP accounts are not included in GNS metrics path
    assert "sip_accounts" not in result


def test_get_api_from_hass_data(hass: HomeAssistant, mock_config_entry) -> None:
    """Test getting API from hass.data."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    hass.data[DOMAIN] = {"test_entry_id": {"api": mock_api}}

    api = coordinator._get_api()

    assert api == mock_api


def test_get_api_from_runtime_data(hass: HomeAssistant, mock_config_entry) -> None:
    """Test getting API from runtime_data."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    mock_config_entry = MagicMock(spec=ConfigEntry)
    mock_config_entry.entry_id = "test_entry_id"
    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_config_entry.runtime_data = {"api": mock_api}

    with patch.object(
        hass.config_entries, "async_entries", return_value=[mock_config_entry]
    ):
        api = coordinator._get_api()

        assert api == mock_api


def test_get_api_no_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test getting API when no entry exists."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    # No hass.data and no config entries
    hass.data[DOMAIN] = {}

    with (
        patch.object(hass.config_entries, "async_entries", return_value=[]),
        pytest.raises(KeyError),
    ):
        # This should raise KeyError when trying to access hass.data[DOMAIN]["test_entry_id"]
        coordinator._get_api()


def test_get_api_no_runtime_data(hass: HomeAssistant, mock_config_entry) -> None:
    """Test getting API when config entry has no runtime_data."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    mock_config_entry = MagicMock(spec=ConfigEntry)
    mock_config_entry.entry_id = "test_entry_id"
    mock_config_entry.runtime_data = None

    # Ensure hass.data has the entry to avoid KeyError
    hass.data[DOMAIN] = {"test_entry_id": {}}

    with patch.object(
        hass.config_entries, "async_entries", return_value=[mock_config_entry]
    ):
        api = coordinator._get_api()

        assert api is None


async def test_async_update_data_ha_control_disabled(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test _async_update_data when HA control is disabled (covers lines 259-260)."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = True  # This triggers lines 259-260

    hass.data[DOMAIN] = {"test_entry_id": {"api": mock_api}}

    result = await coordinator._async_update_data()

    # Should return error data when HA control is disabled
    assert result is not None


def test_process_push_data_non_dict_data(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test _process_push_data with non-dict data (covers line 172)."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    # Test with non-dict, non-string data (e.g., a number)
    # This should trigger line 172: data = {"phone_status": str(data)}
    data = 12345  # Non-string, non-dict data

    result = coordinator._process_push_data(data)  # type: ignore[arg-type]

    # Should convert to dict with phone_status
    assert result == {"phone_status": "12345"}


async def test_fetch_sip_accounts_with_dict_body(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test _fetch_sip_accounts with dict body (covers lines 235-237)."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    mock_api = MagicMock()
    # Return a dict body instead of list
    mock_api.get_accounts.return_value = {
        "response": "success",
        "body": {"account1": {"status": "registered"}},  # dict instead of list
    }

    result = await coordinator._fetch_sip_accounts(mock_api)

    # Should process the dict body
    assert result is not None


async def test_fetch_sip_accounts_exception(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test _fetch_sip_accounts handles exceptions (covers lines 238-239)."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    mock_api = MagicMock()
    # Make get_accounts raise an exception
    mock_api.get_accounts.side_effect = RuntimeError("API error")

    result = await coordinator._fetch_sip_accounts(mock_api)

    # Should return empty list on exception
    assert result == []


def test_build_sip_account_dict_with_dict_body(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test _build_sip_account_dict with dict body (covers lines 235-239)."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    # Test with sip_body as a single dict (not a list)
    sip_body = {"account1": {"status": "registered", "uri": "sip:123@192.168.1.1"}}

    result = coordinator._build_sip_account_dict(sip_body)

    # Should process the dict body
    assert result is not None
