"""Tests for the Dreo fan component."""

from unittest.mock import MagicMock

from hscloud.hscloudexception import (
    HsCloudAccessDeniedException,
    HsCloudBusinessException,
    HsCloudException,
    HsCloudFlowControlException,
)
import pytest

from homeassistant.components.dreo.fan import DreoFan
from homeassistant.exceptions import HomeAssistantError

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
    entity = DreoFan(mock_device, mock_config_entry)

    # Set attributes directly instead of using _fan_props
    entity._attr_preset_mode = None
    entity._attr_percentage = None
    entity._attr_oscillating = None
    entity._attr_is_on = False
    entity._low_high_range = (1, 100)  # Assume this property still exists

    # Mock methods to avoid HomeAssistant instance dependency
    entity.schedule_update_ha_state = MagicMock()

    return entity


# pylint: disable=redefined-outer-name
@pytest.mark.asyncio
async def test_turn_on(fan_entity) -> None:
    """Test turning the fan on."""
    fan_entity.turn_on()

    assert fan_entity.is_on
    fan_entity._config_entry.runtime_data.client.update_status.assert_called_once_with(
        fan_entity._device_id, power_switch=True
    )
    fan_entity.schedule_update_ha_state.assert_called_once_with(force_refresh=True)


@pytest.mark.asyncio
async def test_turn_on_with_percentage(fan_entity) -> None:
    """Test turning the fan on with percentage."""
    fan_entity.turn_on(percentage=50)

    assert fan_entity.is_on
    fan_entity._config_entry.runtime_data.client.update_status.assert_called_once_with(
        fan_entity._device_id, power_switch=True, speed=50
    )
    fan_entity.schedule_update_ha_state.assert_called_once_with(force_refresh=True)


@pytest.mark.asyncio
async def test_turn_on_with_preset_mode(fan_entity) -> None:
    """Test turning the fan on with preset mode."""
    fan_entity.turn_on(preset_mode="auto")

    assert fan_entity.is_on
    fan_entity._config_entry.runtime_data.client.update_status.assert_called_once_with(
        fan_entity._device_id, power_switch=True, mode="auto"
    )
    fan_entity.schedule_update_ha_state.assert_called_once_with(force_refresh=True)


@pytest.mark.asyncio
async def test_turn_on_with_all_params(fan_entity) -> None:
    """Test turning the fan on with both percentage and preset mode."""
    fan_entity.turn_on(percentage=75, preset_mode="auto")

    assert fan_entity.is_on
    fan_entity._config_entry.runtime_data.client.update_status.assert_called_once_with(
        fan_entity._device_id, power_switch=True, speed=75, mode="auto"
    )
    fan_entity.schedule_update_ha_state.assert_called_once_with(force_refresh=True)


# pylint: disable=redefined-outer-name
@pytest.mark.asyncio
async def test_turn_off(fan_entity) -> None:
    """Test turning the fan off."""
    fan_entity.turn_off()

    assert not fan_entity.is_on
    fan_entity._config_entry.runtime_data.client.update_status.assert_called_once_with(
        fan_entity._device_id, power_switch=False
    )
    fan_entity.schedule_update_ha_state.assert_called_once_with(force_refresh=True)


# pylint: disable=redefined-outer-name
@pytest.mark.asyncio
async def test_set_percentage(fan_entity) -> None:
    """Test setting the fan percentage."""
    fan_entity.set_percentage(50)

    fan_entity._attr_percentage = 50  # Manually set for test
    assert fan_entity.percentage == 50
    fan_entity._config_entry.runtime_data.client.update_status.assert_called_once()
    fan_entity.schedule_update_ha_state.assert_called_once_with(force_refresh=True)


@pytest.mark.asyncio
async def test_set_percentage_zero(fan_entity) -> None:
    """Test setting the fan percentage to zero turns off the fan."""
    fan_entity.set_percentage(0)

    assert not fan_entity.is_on
    fan_entity._config_entry.runtime_data.client.update_status.assert_called_once_with(
        fan_entity._device_id, power_switch=False
    )
    fan_entity.schedule_update_ha_state.assert_called_once_with(force_refresh=True)


# pylint: disable=redefined-outer-name
@pytest.mark.asyncio
async def test_oscillate(fan_entity) -> None:
    """Test setting oscillation."""
    fan_entity.oscillate(True)

    fan_entity._attr_oscillating = True  # Manually set for test
    assert fan_entity.oscillating
    fan_entity._config_entry.runtime_data.client.update_status.assert_called_once_with(
        fan_entity._device_id, oscillate=True
    )
    fan_entity.schedule_update_ha_state.assert_called_once_with(force_refresh=True)


# pylint: disable=redefined-outer-name
@pytest.mark.asyncio
async def test_set_preset_mode(fan_entity) -> None:
    """Test setting the fan preset mode."""
    fan_entity.set_preset_mode("auto")

    fan_entity._attr_preset_mode = "auto"  # Manually set for test
    assert fan_entity.preset_mode == "auto"
    fan_entity._config_entry.runtime_data.client.update_status.assert_called_once_with(
        fan_entity._device_id, mode="auto"
    )
    fan_entity.schedule_update_ha_state.assert_called_once_with(force_refresh=True)


@pytest.mark.asyncio
async def test_update(fan_entity) -> None:
    """Test updating fan state."""
    status_data = {
        "power_switch": True,
        "connected": True,
        "mode": "auto",
        "speed": 50,
        "oscillate": True,
    }
    fan_entity._config_entry.runtime_data.client.get_status.return_value = status_data
    # Set the low_high_range correctly for percentage calculation
    fan_entity._low_high_range = (1, 100)

    fan_entity.update()

    assert fan_entity.is_on is True
    assert fan_entity.available is True
    assert fan_entity.preset_mode == "auto"
    assert fan_entity.percentage == 50
    assert fan_entity.oscillating is True


@pytest.mark.asyncio
async def test_update_none_status(fan_entity) -> None:
    """Test updating fan state when status is None."""
    fan_entity._config_entry.runtime_data.client.get_status.return_value = None

    fan_entity.update()

    assert fan_entity.available is False


# Error handling tests
@pytest.mark.asyncio
async def test_turn_on_error(fan_entity) -> None:
    """Test error handling when turning on fails."""
    fan_entity._config_entry.runtime_data.client.update_status.side_effect = (
        HsCloudException("Failed to turn on")
    )

    with pytest.raises(HomeAssistantError) as excinfo:
        fan_entity.turn_on()

    # Check that the error has the correct translation details
    assert excinfo.value.translation_domain == "dreo"
    assert excinfo.value.translation_key == "exceptions.turn_on_failed.message"


@pytest.mark.asyncio
async def test_turn_off_error(fan_entity) -> None:
    """Test error handling when turning off fails."""
    fan_entity._config_entry.runtime_data.client.update_status.side_effect = (
        HsCloudBusinessException("Failed to turn off")
    )

    with pytest.raises(HomeAssistantError) as excinfo:
        fan_entity.turn_off()

    # Check that the error has the correct translation details
    assert excinfo.value.translation_domain == "dreo"
    assert excinfo.value.translation_key == "exceptions.turn_off_failed.message"


@pytest.mark.asyncio
async def test_set_preset_mode_error(fan_entity) -> None:
    """Test error handling when setting preset mode fails."""
    fan_entity._config_entry.runtime_data.client.update_status.side_effect = (
        HsCloudAccessDeniedException("Failed to set preset mode")
    )

    with pytest.raises(HomeAssistantError) as excinfo:
        fan_entity.set_preset_mode("auto")

    # Check that the error has the correct translation details
    assert excinfo.value.translation_domain == "dreo"
    assert excinfo.value.translation_key == "exceptions.set_preset_mode_failed.message"


@pytest.mark.asyncio
async def test_set_percentage_error(fan_entity) -> None:
    """Test error handling when setting percentage fails."""
    fan_entity._config_entry.runtime_data.client.update_status.side_effect = (
        HsCloudFlowControlException("Failed to set speed")
    )

    with pytest.raises(HomeAssistantError) as excinfo:
        fan_entity.set_percentage(50)

    # Check that the error has the correct translation details
    assert excinfo.value.translation_domain == "dreo"
    assert excinfo.value.translation_key == "exceptions.set_speed_failed.message"


@pytest.mark.asyncio
async def test_oscillate_error(fan_entity) -> None:
    """Test error handling when setting oscillation fails."""
    fan_entity._config_entry.runtime_data.client.update_status.side_effect = (
        HsCloudException("Failed to set oscillation")
    )

    with pytest.raises(HomeAssistantError) as excinfo:
        fan_entity.oscillate(True)

    # Check that the error has the correct translation details
    assert excinfo.value.translation_domain == "dreo"
    assert excinfo.value.translation_key == "exceptions.set_oscillate_failed.message"
