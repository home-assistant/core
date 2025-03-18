"""Tests for the Dreo fan component."""

from unittest.mock import MagicMock

import pytest

from tests.common import MockConfigEntry


@pytest.fixture
def mock_device():
    """Return a mock Dreo device."""
    return {
        "deviceSn": "test-device-id",
        "deviceName": "Test Fan",
        "model": "DR-HTF001S",
        "moduleFirmwareVersion": "1.0.0",
        "mcuFirmwareVersion": "1.0.0",
    }


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    config_entry = MockConfigEntry(domain="dreo")
    config_entry.runtime_data = MagicMock()
    config_entry.runtime_data.client = MagicMock()
    return config_entry


# pylint: disable=import-outside-toplevel,protected-access,redefined-outer-name
@pytest.fixture
def fan_entity(mock_device, mock_config_entry):
    """Return a configured fan entity."""
    from homeassistant.components.dreo.fan import DreoFanHA

    entity = DreoFanHA(mock_device, mock_config_entry)
    entity._fan_props = {
        "state": False,
        "preset_mode": None,
        "percentage": None,
        "oscillating": None,
    }

    entity.get_device_id = lambda: entity._device_id
    entity.get_config_entry = lambda: entity._config_entry

    return entity


# pylint: disable=redefined-outer-name
@pytest.mark.asyncio
async def test_turn_on(fan_entity) -> None:
    """Test turning the fan on."""
    fan_entity.turn_on()

    assert fan_entity.is_on
    fan_entity.get_config_entry().runtime_data.client.update_status.assert_called_once_with(
        fan_entity.get_device_id(), power_switch=True
    )


# pylint: disable=redefined-outer-name
@pytest.mark.asyncio
async def test_turn_off(fan_entity) -> None:
    """Test turning the fan off."""
    fan_entity.turn_off()

    assert not fan_entity.is_on
    fan_entity.get_config_entry().runtime_data.client.update_status.assert_called_once_with(
        fan_entity.get_device_id(), power_switch=False
    )


# pylint: disable=redefined-outer-name
@pytest.mark.asyncio
async def test_set_percentage(fan_entity) -> None:
    """Test setting the fan percentage."""
    fan_entity.set_percentage(50)

    assert fan_entity.percentage == 50
    fan_entity.get_config_entry().runtime_data.client.update_status.assert_called_once()


# pylint: disable=redefined-outer-name
@pytest.mark.asyncio
async def test_oscillate(fan_entity) -> None:
    """Test setting oscillation."""
    fan_entity.oscillate(True)

    assert fan_entity.oscillating
    fan_entity.get_config_entry().runtime_data.client.update_status.assert_called_once_with(
        fan_entity.get_device_id(), oscillate=True
    )


# pylint: disable=redefined-outer-name
@pytest.mark.asyncio
async def test_set_preset_mode(fan_entity) -> None:
    """Test setting the fan preset mode."""
    fan_entity.set_preset_mode("auto")

    assert fan_entity.preset_mode == "auto"
    fan_entity.get_config_entry().runtime_data.client.update_status.assert_called_once_with(
        fan_entity.get_device_id(), mode="auto"
    )
