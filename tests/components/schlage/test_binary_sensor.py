"""Test Schlage binary_sensor."""

from datetime import timedelta
from unittest.mock import Mock

from pyschlage.exceptions import UnknownError

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed


async def test_keypad_disabled_binary_sensor(
    hass: HomeAssistant, mock_lock: Mock, mock_added_config_entry: ConfigEntry
) -> None:
    """Test the keypad_disabled binary_sensor."""
    mock_lock.keypad_disabled.reset_mock()
    mock_lock.keypad_disabled.return_value = True

    # Make the coordinator refresh data.
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done(wait_background_tasks=True)

    keypad = hass.states.get("binary_sensor.vault_door_keypad_disabled")
    assert keypad is not None
    assert keypad.state == "on"
    assert keypad.attributes["device_class"] == BinarySensorDeviceClass.PROBLEM

    mock_lock.keypad_disabled.assert_called_once_with([])


async def test_keypad_disabled_binary_sensor_use_previous_logs_on_failure(
    hass: HomeAssistant, mock_lock: Mock, mock_added_config_entry: ConfigEntry
) -> None:
    """Test the keypad_disabled binary_sensor."""
    mock_lock.keypad_disabled.reset_mock()
    mock_lock.keypad_disabled.return_value = True
    mock_lock.logs.reset_mock()
    mock_lock.logs.side_effect = UnknownError("Cannot load logs")

    # Make the coordinator refresh data.
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done(wait_background_tasks=True)

    keypad = hass.states.get("binary_sensor.vault_door_keypad_disabled")
    assert keypad is not None
    assert keypad.state == "on"
    assert keypad.attributes["device_class"] == BinarySensorDeviceClass.PROBLEM

    mock_lock.keypad_disabled.assert_called_once_with([])
