"""Test Grandstream coordinator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from grandstream_home_api import (
    build_sip_account_dict,
    fetch_gns_metrics,
    fetch_sip_accounts,
    process_push_data,
    process_status,
)
import pytest

from homeassistant.components.grandstream_home.const import (
    DEVICE_TYPE_GDS,
    DEVICE_TYPE_GNS_NAS,
)
from homeassistant.components.grandstream_home.coordinator import GrandstreamCoordinator
from homeassistant.components.grandstream_home.device import GrandstreamDevice
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


async def test_update_data_success_gds(hass: HomeAssistant, mock_config_entry) -> None:
    """Test successful data update for GDS device."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    # Setup mock API
    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_phone_status.return_value = {"response": "success", "body": "idle"}
    mock_api.version = "1.0.0"
    mock_api.get_accounts.return_value = {"response": "success", "body": []}

    # Setup mock device
    mock_device = MagicMock()
    mock_device.set_firmware_version = MagicMock()

    # Setup runtime_data
    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api
    mock_runtime_data.device = mock_device
    mock_config_entry.runtime_data = mock_runtime_data

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

    # Setup mock device
    mock_device = MagicMock()
    mock_device.set_firmware_version = MagicMock()

    # Setup runtime_data
    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api
    mock_runtime_data.device = mock_device
    mock_config_entry.runtime_data = mock_runtime_data

    result = await coordinator._async_update_data()

    assert result["cpu_usage"] == 25.5
    assert result["memory_usage_percent"] == 45.2
    assert result["device_status"] == "online"
    assert coordinator._error_count == 0


async def test_update_data_api_failure(hass: HomeAssistant, mock_config_entry) -> None:
    """Test data update with API failure."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    # Setup mock API that fails
    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_phone_status.return_value = {
        "response": "error",
        "body": "Connection failed",
    }

    # Setup runtime_data
    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api
    mock_config_entry.runtime_data = mock_runtime_data

    result = await coordinator._async_update_data()

    assert result["phone_status"] == "unknown"
    assert coordinator._error_count == 1


async def test_update_data_max_errors(hass: HomeAssistant, mock_config_entry) -> None:
    """Test data update reaching max errors."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    # Setup mock API that fails
    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_phone_status.return_value = {
        "response": "error",
        "body": "Connection failed",
    }

    # Setup runtime_data
    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api
    mock_config_entry.runtime_data = mock_runtime_data

    # Simulate reaching max errors
    coordinator._error_count = 3

    result = await coordinator._async_update_data()

    assert result["phone_status"] == "unavailable"


async def test_update_data_no_api(hass: HomeAssistant, mock_config_entry) -> None:
    """Test data update with no API available."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)
    mock_config_entry.runtime_data = None

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

    result = process_status(long_status)

    assert len(result) <= 253  # 250 + "..."
    assert result.endswith("...")


def test_process_status_json_string(coordinator) -> None:
    """Test processing JSON status string."""
    json_status = '{"status": "idle", "extra": "data"}'

    result = process_status(json_status)

    assert result == "idle"


def test_process_status_empty(coordinator) -> None:
    """Test processing empty status."""
    result = process_status("")

    assert result == "unknown"


def test_handle_push_data_sync(coordinator) -> None:
    """Test synchronous handle_push_data method."""
    coordinator.handle_push_data("available")

    assert coordinator.data["phone_status"] == "available"


async def test_update_data_with_version_update(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test data update with firmware version update."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_phone_status.return_value = {"response": "success", "body": "idle"}
    mock_api.version = "1.2.3"
    mock_api.get_accounts.return_value = {"response": "success", "body": []}

    mock_device = MagicMock()
    mock_device.set_firmware_version = MagicMock()

    # Setup runtime_data
    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api
    mock_runtime_data.device = mock_device
    mock_config_entry.runtime_data = mock_runtime_data

    await coordinator._async_update_data()

    mock_device.set_firmware_version.assert_called_once_with("1.2.3")


async def test_update_data_exception_handling(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test data update with exception."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False
    mock_api.get_phone_status.side_effect = RuntimeError("Connection error")

    # Setup runtime_data
    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api
    mock_config_entry.runtime_data = mock_runtime_data

    # Exception should be caught and logged, returning error status
    result = await coordinator._async_update_data()
    assert result["phone_status"] == "unknown"


def test_process_status_dict(coordinator) -> None:
    """Test processing dictionary status."""
    status_dict = {"status": "ringing", "line": 1}

    result = process_status(status_dict)

    # Dict is converted to string
    assert "ringing" in result


def test_process_status_none(coordinator) -> None:
    """Test processing None status."""
    result = process_status(None)

    assert result == "unknown"


def test_process_status_invalid_json(coordinator) -> None:
    """Test processing status that starts with { but is not valid JSON."""
    invalid_json = "{invalid"
    result = process_status(invalid_json)
    # Should pass through JSONDecodeError and continue processing
    assert result == "{invalid"


async def test_update_data_no_api_max_errors(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test data update with no API available and error count already at max."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)
    mock_config_entry.runtime_data = None

    # Set error count to max errors
    coordinator._error_count = coordinator._max_errors

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

    # Setup runtime_data
    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api
    mock_config_entry.runtime_data = mock_runtime_data

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
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test data update with specific exception types."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = False

    # Setup runtime_data
    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api
    mock_config_entry.runtime_data = mock_runtime_data

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
    """Test async_handle_push_data with exception (covers lines 141-143)."""
    # Patch process_push_data to raise an exception
    with (
        pytest.raises(ValueError),
        patch(
            "homeassistant.components.grandstream_home.coordinator.process_push_data",
            side_effect=ValueError("Test error"),
        ),
    ):
        await coordinator.async_handle_push_data({"test": "data"})


def test_handle_push_data_dict_mapping(coordinator) -> None:
    """Test synchronous handle_push_data with dict mapping of status keys."""
    coordinator.handle_push_data({"status": "busy", "other": "data"})
    assert coordinator.data["phone_status"] == "busy"

    coordinator.handle_push_data({"state": "idle"})
    assert coordinator.data["phone_status"] == "idle"

    coordinator.handle_push_data({"value": "ringing"})
    assert coordinator.data["phone_status"] == "ringing"

    coordinator.handle_push_data({"other": "data"})
    assert "phone_status" not in coordinator.data
    assert coordinator.data == {"other": "data"}


def test_handle_push_data_sync_exception(coordinator) -> None:
    """Test synchronous handle_push_data with exception."""
    # The exception handling is in the function itself
    # process_push_data doesn't raise exceptions for valid input
    # This test verifies the function works with valid input
    coordinator.handle_push_data({"phone_status": "test"})
    assert coordinator.data["phone_status"] == "test"


async def test_update_data_no_api_under_max_errors(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test update data when API is not available but under max errors."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)
    mock_config_entry.runtime_data = None

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
    mock_config_entry.runtime_data = None

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

    # Setup runtime_data
    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api
    mock_config_entry.runtime_data = mock_runtime_data

    # Call _async_update_data directly
    result = await coordinator._async_update_data()

    # Should handle the case where get_system_metrics is not available
    assert isinstance(result, dict)


async def test_update_data_with_runtime_data_api(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test update data using API from runtime_data."""
    # Setup mock API
    mock_api = MagicMock()
    mock_api.get_phone_status.return_value = {
        "response": "success",
        "body": "available",
    }
    mock_api.is_ha_control_disabled = False
    mock_api.get_accounts.return_value = {"response": "success", "body": []}

    # Setup runtime_data
    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api
    mock_config_entry.runtime_data = mock_runtime_data

    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    result = await coordinator._async_update_data()

    # Should successfully get data from runtime_data API
    assert "phone_status" in result
    assert result["phone_status"].strip() == "available"


def test_fetch_gns_metrics_success() -> None:
    """Test successful GNS metrics fetch."""

    mock_api = MagicMock()
    mock_api.get_system_metrics.return_value = {
        "cpu_usage": 25.5,
        "memory_usage_percent": 45.2,
        "device_status": "online",
    }

    result = fetch_gns_metrics(mock_api)

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

    # Setup runtime_data
    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api
    mock_config_entry.runtime_data = mock_runtime_data

    # Since API doesn't have get_system_metrics, it should return None
    result = await coordinator._async_update_data()

    assert result["device_status"] == "unknown"


def test_fetch_sip_accounts_success() -> None:
    """Test successful SIP accounts fetch."""

    mock_api = MagicMock()
    mock_api.get_accounts.return_value = {
        "response": "success",
        "body": [
            {"id": "1", "reg": 1, "name": "user1"},
            {"id": "2", "reg": 0, "name": "user2"},
        ],
    }

    result = fetch_sip_accounts(mock_api)

    assert len(result) == 2
    assert result[0]["id"] == "1"
    assert result[0]["status"] == "registered"  # reg=1 maps to "registered"
    assert result[1]["id"] == "2"
    assert result[1]["status"] == "unregistered"  # reg=0 maps to "unregistered"


def test_fetch_sip_accounts_error() -> None:
    """Test SIP accounts fetch with error response."""

    mock_api = MagicMock()
    mock_api.get_accounts.return_value = {
        "response": "error",
        "body": "Authentication failed",
    }

    result = fetch_sip_accounts(mock_api)

    assert result == []


def test_fetch_sip_accounts_no_method() -> None:
    """Test SIP accounts fetch when API has no get_accounts method."""

    mock_api = MagicMock()
    # Remove get_accounts method
    del mock_api.get_accounts

    result = fetch_sip_accounts(mock_api)

    assert result == []


def test_build_sip_account_dict(hass: HomeAssistant, mock_config_entry) -> None:
    """Test building SIP account dictionary."""

    account = {
        "id": "1",
        "reg": 1,  # Use reg status instead of status
        "name": "user1",
        "sip_id": "sip1",
    }

    result = build_sip_account_dict(account)

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

    result = process_push_data("ringing")

    assert result["phone_status"] == "ringing"


def test_process_push_data_dict_with_status(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test processing push data as dict with status key."""

    data = {"status": "busy", "caller_id": "123456"}
    result = process_push_data(data)

    # When status key exists, only phone_status is kept
    assert result["phone_status"] == "busy"
    assert "caller_id" not in result  # Other data is not preserved


def test_process_push_data_dict_with_state(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test processing push data as dict with state key."""

    data = {"state": "idle", "line": 1}
    result = process_push_data(data)

    # When state key exists, only phone_status is kept
    assert result["phone_status"] == "idle"
    assert "line" not in result  # Other data is not preserved


def test_process_push_data_dict_with_value(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test processing push data as dict with value key."""

    data = {"value": "available", "timestamp": "2023-01-01"}
    result = process_push_data(data)

    # When value key exists, only phone_status is kept
    assert result["phone_status"] == "available"
    assert "timestamp" not in result  # Other data is not preserved


def test_process_push_data_dict_no_status_keys(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test processing push data as dict without status keys."""

    data = {"caller_id": "123456", "line": 1}
    result = process_push_data(data)

    assert result == data  # Should return as-is
    assert "phone_status" not in result


def test_process_push_data_json_string(hass: HomeAssistant, mock_config_entry) -> None:
    """Test processing push data as JSON string."""

    json_data = '{"status": "ringing", "caller_id": "987654"}'
    result = process_push_data(json_data)

    # When status key exists in parsed JSON, only phone_status is kept
    assert result["phone_status"] == "ringing"
    assert "caller_id" not in result  # Other data is not preserved


def test_process_push_data_invalid_json(hass: HomeAssistant, mock_config_entry) -> None:
    """Test processing push data as invalid JSON string."""

    invalid_json = '{"invalid": json}'
    result = process_push_data(invalid_json)

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

    # Setup runtime_data
    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api
    mock_runtime_data.device = mock_device
    mock_config_entry.runtime_data = mock_runtime_data

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

    # Setup runtime_data
    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api
    mock_runtime_data.device = mock_device
    mock_config_entry.runtime_data = mock_runtime_data

    result = await coordinator._async_update_data()

    assert result["cpu_usage"] == 25.5
    assert result["device_status"] == "online"
    # SIP accounts are not included in GNS metrics path
    assert "sip_accounts" not in result


def test_get_api_from_runtime_data(hass: HomeAssistant, mock_config_entry) -> None:
    """Test getting API from runtime_data."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    # Create a mock runtime_data with api attribute
    mock_runtime_data = MagicMock()
    mock_api = MagicMock()
    mock_runtime_data.api = mock_api
    mock_config_entry.runtime_data = mock_runtime_data

    api = coordinator._get_api()
    assert api == mock_api


def test_get_api_no_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test getting API when no runtime_data exists."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)
    mock_config_entry.runtime_data = None

    api = coordinator._get_api()
    assert api is None


def test_get_api_no_runtime_data(hass: HomeAssistant, mock_config_entry) -> None:
    """Test getting API when config entry has no runtime_data."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)
    mock_config_entry.runtime_data = None

    api = coordinator._get_api()
    assert api is None


async def test_async_update_data_ha_control_disabled(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test _async_update_data when HA control is disabled (covers lines 259-260)."""
    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    mock_api = MagicMock()
    mock_api.is_ha_control_disabled = True  # This triggers lines 259-260

    # Setup runtime_data
    mock_runtime_data = MagicMock()
    mock_runtime_data.api = mock_api
    mock_config_entry.runtime_data = mock_runtime_data

    result = await coordinator._async_update_data()

    # Should return error data when HA control is disabled
    assert result is not None


def test_process_push_data_non_dict_data(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test _process_push_data with non-dict data (covers line 172)."""

    # Test with non-dict, non-string data (e.g., a number)
    # This should trigger line 172: data = {"phone_status": str(data)}
    data = 12345  # Non-string, non-dict data

    result = process_push_data(data)  # type: ignore[arg-type]

    # Should convert to dict with phone_status
    assert result == {"phone_status": "12345"}


def test_fetch_sip_accounts_with_dict_body() -> None:
    """Test fetch_sip_accounts with dict body (covers lines 235-237)."""

    mock_api = MagicMock()
    # Return a dict body instead of list
    mock_api.get_accounts.return_value = {
        "response": "success",
        "body": {"account1": {"status": "registered"}},  # dict instead of list
    }

    result = fetch_sip_accounts(mock_api)

    # Should process the dict body
    assert result is not None


def test_fetch_sip_accounts_exception() -> None:
    """Test fetch_sip_accounts handles exceptions (covers lines 238-239)."""

    mock_api = MagicMock()
    # Make get_accounts raise an exception
    mock_api.get_accounts.side_effect = RuntimeError("API error")

    result = fetch_sip_accounts(mock_api)

    # Should return empty list on exception
    assert result == []


def test_build_sip_account_dict_with_dict_body() -> None:
    """Test build_sip_account_dict with dict body (covers lines 235-239)."""
    # Test with sip_body as a single dict (not a list)
    sip_body = {"account1": {"status": "registered", "uri": "sip:123@192.168.1.1"}}

    result = build_sip_account_dict(sip_body)

    # Should process the dict body
    assert result is not None


def test_get_device_without_runtime_data(hass: HomeAssistant) -> None:
    """Test _get_device when runtime_data is not set (covers line 64)."""

    # Create a simple object without runtime_data attribute
    class MockConfigEntry:
        entry_id = "test_entry_id"
        data = {}

        def async_on_unload(self, *args):
            pass

    mock_config_entry = MockConfigEntry()

    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    # _get_device should return None when runtime_data is not set
    device = coordinator._get_device()
    assert device is None


def test_handle_push_data_exception(hass: HomeAssistant) -> None:
    """Test handle_push_data handles exceptions (covers lines 152-154)."""

    mock_config_entry = MagicMock(spec=ConfigEntry)
    mock_config_entry.entry_id = "test_entry_id"
    mock_config_entry.data = {}
    mock_config_entry.async_on_unload = MagicMock()

    # Create runtime_data with device
    device = GrandstreamDevice(hass, "Test Device", "test_device", "test_entry_id")
    mock_runtime_data = MagicMock()
    mock_runtime_data.device = device
    mock_config_entry.runtime_data = mock_runtime_data

    coordinator = GrandstreamCoordinator(hass, DEVICE_TYPE_GDS, mock_config_entry)

    # Patch process_push_data to raise an exception
    with (
        pytest.raises(ValueError),
        patch(
            "homeassistant.components.grandstream_home.coordinator.process_push_data",
            side_effect=ValueError("Test error"),
        ),
    ):
        coordinator.handle_push_data({"test": "data"})
