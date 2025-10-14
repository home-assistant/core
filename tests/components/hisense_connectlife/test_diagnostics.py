"""Test diagnostics for Hisense AC Plugin."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.hisense_connectlife.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)


@pytest.mark.asyncio
async def test_get_config_entry_diagnostics_no_coordinator(mock_hass, mock_config_entry):
    """Test diagnostics when coordinator is not found."""
    mock_hass.data = {}
    
    result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
    
    assert result == {"error": "Coordinator not found"}


@pytest.mark.asyncio
async def test_get_config_entry_diagnostics_with_coordinator(mock_hass, mock_config_entry, mock_coordinator, mock_device_info):
    """Test diagnostics with coordinator."""
    mock_hass.data = {mock_config_entry.domain: {mock_config_entry.entry_id: mock_coordinator}}
    mock_coordinator._devices = {"test_device_1": mock_device_info}
    mock_coordinator.api_client = MagicMock()
    mock_coordinator.api_client.parsers = {"test_device_1": MagicMock()}
    mock_coordinator.api_client.static_data = {"test_device_1": {}}
    
    result = await async_get_config_entry_diagnostics(mock_hass, mock_config_entry)
    
    assert "config_entry" in result
    assert "coordinator" in result
    assert "devices" in result
    assert "api_client" in result
    assert "websocket" in result
    
    # Check that sensitive data is redacted
    assert "access_token" not in str(result)
    assert "refresh_token" not in str(result)
    assert "puid" not in str(result)


@pytest.mark.asyncio
async def test_get_device_diagnostics_no_coordinator(mock_hass, mock_config_entry):
    """Test device diagnostics when coordinator is not found."""
    mock_hass.data = {}
    
    result = await async_get_device_diagnostics(mock_hass, mock_config_entry, "test_device_1")
    
    assert result == {"error": "Coordinator not found"}


@pytest.mark.asyncio
async def test_get_device_diagnostics_device_not_found(mock_hass, mock_config_entry, mock_coordinator):
    """Test device diagnostics when device is not found."""
    mock_hass.data = {mock_config_entry.domain: {mock_config_entry.entry_id: mock_coordinator}}
    mock_coordinator.get_device.return_value = None
    
    result = await async_get_device_diagnostics(mock_hass, mock_config_entry, "test_device_1")
    
    assert result == {"error": "Device test_device_1 not found"}


@pytest.mark.asyncio
async def test_get_device_diagnostics_success(mock_hass, mock_config_entry, mock_coordinator, mock_device_info):
    """Test successful device diagnostics."""
    mock_hass.data = {mock_config_entry.domain: {mock_config_entry.entry_id: mock_coordinator}}
    mock_coordinator.get_device.return_value = mock_device_info
    mock_coordinator.api_client = MagicMock()
    mock_coordinator.api_client.parsers = {"test_device_1": MagicMock()}
    mock_coordinator.api_client.parsers["test_device_1"].attributes = {"test_attr": "test_value"}
    
    result = await async_get_device_diagnostics(mock_hass, mock_config_entry, "test_device_1")
    
    assert "device" in result
    assert "parser" in result
    assert result["device"]["device_id"] == "test_device_1"
    assert result["device"]["name"] == "Test AC Unit"
    
    # Check that sensitive data is redacted
    assert "access_token" not in str(result)
    assert "refresh_token" not in str(result)
    assert "puid" not in str(result)


@pytest.mark.asyncio
async def test_diagnostics_redaction():
    """Test that sensitive data is properly redacted."""
    from custom_components.hisense_connectlife.diagnostics import TO_REDACT
    
    # Test data with sensitive information
    test_data = {
        "access_token": "secret_token",
        "refresh_token": "secret_refresh",
        "puid": "secret_puid",
        "deviceId": "secret_device_id",
        "sourceId": "secret_source_id",
        "appId": "secret_app_id",
        "timeStamp": "1234567890",
        "randStr": "secret_random",
        "safe_data": "this_should_not_be_redacted",
        "nested": {
            "access_token": "nested_secret",
            "safe_nested": "this_should_not_be_redacted",
        },
    }
    
    # Mock the redact function
    with patch("custom_components.hisense_connectlife.diagnostics.async_redact_data") as mock_redact:
        mock_redact.return_value = test_data
        
        # The actual redaction would be done by Home Assistant's async_redact_data
        # We just verify that our TO_REDACT list contains the expected keys
        for key in ["access_token", "refresh_token", "puid", "deviceId", "sourceId", "appId", "timeStamp", "randStr"]:
            assert key in TO_REDACT
