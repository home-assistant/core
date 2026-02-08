"""Tests for the VeSyncBaseEntity."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.vesync.entity import VeSyncBaseEntity
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_device():
    """Create a mock VeSync device."""
    device = MagicMock()
    device.device_name = "Test Device"
    device.cid = "test_cid"
    device.sub_device_no = None
    device.device_type = "Test Type"
    device.current_firm_version = "1.0.0"
    device.state = MagicMock()
    device.state.connection_status = "online"
    return device


@pytest.fixture
def mock_coordinator(hass: HomeAssistant):
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.last_update_success = True
    return coordinator


async def test_entity_logs_when_device_becomes_unavailable(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_device, mock_coordinator
) -> None:
    """Test that entity logs when device becomes unavailable."""

    entity = VeSyncBaseEntity(mock_device, mock_coordinator)
    entity.hass = hass
    entity.coordinator.config_entry = MagicMock()

    # Initial state - device is online
    assert entity.available is True

    # Simulate device going offline
    mock_device.state.connection_status = "offline"
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_coordinator_update()

    # Check that unavailable log message was recorded
    assert "The Test Device device is unavailable" in caplog.text
    assert entity._unavailable_logged is True


async def test_entity_logs_when_device_comes_back_online(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_device, mock_coordinator
) -> None:
    """Test that entity logs when device comes back online."""

    entity = VeSyncBaseEntity(mock_device, mock_coordinator)
    entity.hass = hass
    entity.coordinator.config_entry = MagicMock()

    # Simulate device being offline first
    mock_device.state.connection_status = "offline"
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_coordinator_update()
    assert entity._unavailable_logged is True

    # Clear the log to verify new message
    caplog.clear()

    # Simulate device coming back online
    mock_device.state.connection_status = "online"
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_coordinator_update()

    # Check that back online log message was recorded
    assert "The Test Device device is back online" in caplog.text
    assert entity._unavailable_logged is False


async def test_entity_doesnt_log_duplicate_unavailable_messages(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, mock_device, mock_coordinator
) -> None:
    """Test that entity doesn't log duplicate unavailable messages."""

    entity = VeSyncBaseEntity(mock_device, mock_coordinator)
    entity.hass = hass
    entity.coordinator.config_entry = MagicMock()

    # Simulate device going offline
    mock_device.state.connection_status = "offline"
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_coordinator_update()
    first_log_count = len([r for r in caplog.records if "is unavailable" in r.message])
    assert first_log_count == 1

    # Call coordinator update again with device still offline
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_coordinator_update()
    second_log_count = len([r for r in caplog.records if "is unavailable" in r.message])

    # Should not log again
    assert second_log_count == 1
