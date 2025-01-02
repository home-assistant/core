"""Tests for the Dreo Fan component."""

from unittest.mock import MagicMock, patch

from hscloud.hscloudexception import HsCloudBusinessException, HsCloudException
import pytest

from homeassistant.components.dreo.fan import DreoFanHA
from homeassistant.exceptions import ConfigEntryNotReady

# Mock FAN_DEVICE constant
MOCK_FAN_DEVICE = {
    "type": "FAN",
    "config": {
        "TEST_MODEL": {
            "preset_modes": ["auto", "normal", "sleep"],
            "speed_range": (1, 6),
        }
    },
}


@pytest.fixture(autouse=True)
def mock_fan_device():
    """Mock FAN_DEVICE constant."""
    with patch("homeassistant.components.dreo.fan.FAN_DEVICE", MOCK_FAN_DEVICE):
        yield


@pytest.fixture
def mock_device():
    """Create a mock device."""
    return {
        "model": "TEST_MODEL",
        "device_id": "test_device_id",
    }


@pytest.fixture
def mock_config_entry(mock_device):
    """Create a mock config entry."""
    config_entry = MagicMock()
    config_entry.runtime_data = MagicMock()
    config_entry.runtime_data.client = MagicMock()
    # Mock the send_command method to return True
    config_entry.runtime_data.client.send_command.return_value = True
    config_entry.runtime_data.devices = [mock_device]
    return config_entry


@pytest.fixture
def fan(mock_device, mock_config_entry):
    """Create a Dreo fan instance."""

    fan = DreoFanHA(mock_device, mock_config_entry)
    # Ensure device_id is set correctly
    fan._device_id = mock_device["device_id"]
    # Mock _try_command to directly call send_command
    fan._try_command = (
        lambda msg, **kwargs: mock_config_entry.runtime_data.client.send_command(
            fan._device_id, **kwargs
        )
    )
    return fan


def test_turn_on(fan: DreoFanHA) -> None:
    """Test turning the fan on."""
    fan.turn_on()
    assert fan.is_on is True
    fan._config_entry.runtime_data.client.send_command.assert_called_once_with(
        "test_device_id", power_switch=True
    )


def test_turn_off(fan: DreoFanHA) -> None:
    """Test turning the fan off."""
    fan.turn_off()
    assert fan.is_on is False
    fan._config_entry.runtime_data.client.send_command.assert_called_once_with(
        "test_device_id", power_switch=False
    )


def test_set_percentage(fan: DreoFanHA) -> None:
    """Test setting fan speed percentage."""
    fan.set_percentage(50)
    assert fan._attr_percentage == 50
    fan._config_entry.runtime_data.client.send_command.assert_called_once_with(
        "test_device_id",
        speed=3,  # 50% maps to speed 4
    )


def test_oscillate(fan: DreoFanHA) -> None:
    """Test setting oscillation."""
    fan.oscillate(True)
    assert fan._attr_oscillating is True
    fan._config_entry.runtime_data.client.send_command.assert_called_once_with(
        "test_device_id", oscillate=True
    )


def test_set_preset_mode(fan: DreoFanHA) -> None:
    """Test setting preset mode."""
    preset_mode = "auto"
    fan.set_preset_mode(preset_mode)
    assert fan._attr_preset_mode == preset_mode
    fan._config_entry.runtime_data.client.send_command.assert_called_once_with(
        "test_device_id", mode=preset_mode
    )


@pytest.mark.parametrize(
    ("exception", "expected_exception"),
    [
        (HsCloudException(message="Connection error"), type(ConfigEntryNotReady())),
        (
            HsCloudBusinessException(message="Invalid credentials"),
            type(ConfigEntryNotReady()),
        ),
        (Exception("Unexpected error"), type(ConfigEntryNotReady())),
    ],
)
def test_update_errors(
    fan: DreoFanHA, exception: Exception, expected_exception: Exception
) -> None:
    """Test update method error handling."""
    fan._config_entry.runtime_data.client.get_status.side_effect = exception
    with pytest.raises(expected_exception):
        fan.update()


def test_update_success(fan: DreoFanHA) -> None:
    """Test successful update."""
    status = {
        "power_switch": True,
        "mode": "auto",
        "speed": 3,
        "oscillate": True,
        "connected": True,
    }
    fan._config_entry.runtime_data.client.get_status.return_value = status

    fan.update()

    assert fan.is_on is True
    assert fan._attr_preset_mode == "auto"
    assert fan._attr_oscillating is True
    assert fan._attr_available is True


def test_update_device_unavailable(fan: DreoFanHA) -> None:
    """Test update when device is unavailable."""
    fan._config_entry.runtime_data.client.get_status.return_value = None

    fan.update()

    assert fan._attr_available is False
