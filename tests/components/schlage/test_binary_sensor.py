"""Test Schlage binary_sensor."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
from pyschlage.exceptions import UnknownError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.schlage.const import UPDATE_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockSchlageConfigEntry

from tests.common import async_fire_time_changed, snapshot_platform


async def test_binary_sensor_attributes(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockSchlageConfigEntry]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor attributes."""
    with patch("homeassistant.components.schlage.PLATFORMS", [Platform.BINARY_SENSOR]):
        config_entry = await mock_add_config_entry()
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_keypad_disabled_binary_sensor(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_add_config_entry: Callable[[], Awaitable[MockSchlageConfigEntry]],
) -> None:
    """Test the keypad_disabled binary_sensor."""
    mock_lock.keypad_disabled.reset_mock()
    mock_lock.keypad_disabled.return_value = True
    with patch("homeassistant.components.schlage.PLATFORMS", [Platform.BINARY_SENSOR]):
        await mock_add_config_entry()
        keypad = hass.states.get("binary_sensor.vault_door_keypad_disabled")
        assert keypad is not None
        assert keypad.state == STATE_ON
        assert keypad.attributes["device_class"] == BinarySensorDeviceClass.PROBLEM
        mock_lock.keypad_disabled.assert_called_once_with([])


async def test_keypad_disabled_binary_sensor_logs_failure(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_add_config_entry: Callable[[], Awaitable[MockSchlageConfigEntry]],
) -> None:
    """Test the keypad_disabled binary_sensor when loading logs fails on initial setup."""
    mock_lock.keypad_disabled.reset_mock()
    mock_lock.keypad_disabled.return_value = True
    mock_lock.logs.side_effect = UnknownError("Cannot load logs")
    with patch("homeassistant.components.schlage.PLATFORMS", [Platform.BINARY_SENSOR]):
        await mock_add_config_entry()
        keypad = hass.states.get("binary_sensor.vault_door_keypad_disabled")
        assert keypad is not None
        assert keypad.state == STATE_ON
        assert keypad.attributes["device_class"] == BinarySensorDeviceClass.PROBLEM
        mock_lock.keypad_disabled.assert_called_once_with([])


async def test_keypad_disabled_uses_previous_logs_on_refresh_failure(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_add_config_entry: Callable[[], Awaitable[MockSchlageConfigEntry]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that previous logs are used when a coordinator refresh fails to fetch logs."""
    with patch("homeassistant.components.schlage.PLATFORMS", [Platform.BINARY_SENSOR]):
        await mock_add_config_entry()

        keypad = hass.states.get("binary_sensor.vault_door_keypad_disabled")
        assert keypad is not None
        assert keypad.state == STATE_OFF

        mock_lock.keypad_disabled.reset_mock()
        mock_lock.keypad_disabled.return_value = True
        mock_lock.logs.side_effect = UnknownError("Cannot load logs")

        freezer.tick(UPDATE_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

        keypad = hass.states.get("binary_sensor.vault_door_keypad_disabled")
        assert keypad is not None
        assert keypad.state == STATE_ON
        # Previous logs (empty list from initial refresh) are passed when fetch fails.
        mock_lock.keypad_disabled.assert_called_once_with([])
