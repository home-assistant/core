"""Tests for the VeSyncBaseEntity."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.vesync.entity import VeSyncBaseEntity
from homeassistant.core import HomeAssistant


async def test_entity_logs_when_device_becomes_unavailable(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, humidifier, mock_coordinator
) -> None:
    """Test that entity logs when device becomes unavailable."""

    entity = VeSyncBaseEntity(humidifier, mock_coordinator)
    entity.hass = hass
    entity.coordinator.config_entry = MagicMock()

    # Initial state - device is online
    assert entity.available is True

    # Simulate device going offline
    humidifier.state.connection_status = "offline"
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_coordinator_update()

    # Check that unavailable log message was recorded
    assert "The Humidifier 200s device is unavailable" in caplog.text
    assert entity._unavailable_logged is True


async def test_entity_logs_when_device_comes_back_online(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, humidifier, mock_coordinator
) -> None:
    """Test that entity logs when device comes back online."""

    entity = VeSyncBaseEntity(humidifier, mock_coordinator)
    entity.hass = hass
    entity.coordinator.config_entry = MagicMock()

    # Simulate device being offline first
    humidifier.state.connection_status = "offline"
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_coordinator_update()
    assert entity._unavailable_logged is True

    # Clear the log to verify new message
    caplog.clear()

    # Simulate device coming back online
    humidifier.state.connection_status = "online"
    with patch.object(entity, "async_write_ha_state"):
        entity._handle_coordinator_update()

    # Check that back online log message was recorded
    assert "The Humidifier 200s device is back online" in caplog.text
    assert entity._unavailable_logged is False


async def test_entity_doesnt_log_duplicate_unavailable_messages(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, humidifier, mock_coordinator
) -> None:
    """Test that entity doesn't log duplicate unavailable messages."""

    entity = VeSyncBaseEntity(humidifier, mock_coordinator)
    entity.hass = hass
    entity.coordinator.config_entry = MagicMock()

    # Simulate device going offline
    humidifier.state.connection_status = "offline"
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
