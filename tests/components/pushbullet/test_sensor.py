"""Test pushbullet sensor platform."""

from unittest.mock import Mock

import pytest

from homeassistant.components.pushbullet.const import DOMAIN
from homeassistant.components.pushbullet.sensor import (
    SENSOR_TYPES,
    PushBulletNotificationSensor,
)
from homeassistant.const import MAX_LENGTH_STATE_STATE
from homeassistant.core import HomeAssistant

from . import MOCK_CONFIG

from tests.common import MockConfigEntry


def _create_mock_provider() -> Mock:
    """Create a mock pushbullet provider for testing."""
    mock_provider = Mock()
    mock_provider.pushbullet.user_info = {"iden": "test_user_123"}
    return mock_provider


def _get_sensor_description(key: str):
    """Get sensor description by key."""
    for desc in SENSOR_TYPES:
        if desc.key == key:
            return desc
    raise ValueError(f"Sensor description not found for key: {key}")


def _create_test_sensor(
    provider: Mock, sensor_key: str
) -> PushBulletNotificationSensor:
    """Create a test sensor instance with mocked dependencies."""
    description = _get_sensor_description(sensor_key)
    sensor = PushBulletNotificationSensor(
        name="Test Pushbullet", pb_provider=provider, description=description
    )
    # Mock async_write_ha_state to avoid requiring full HA setup
    sensor.async_write_ha_state = Mock()
    return sensor


@pytest.fixture
async def mock_pushbullet_entry(hass: HomeAssistant, requests_mock_fixture):
    """Set up pushbullet integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def test_sensor_truncation_logic() -> None:
    """Test sensor truncation logic for body sensor."""
    provider = _create_mock_provider()
    sensor = _create_test_sensor(provider, "body")

    # Test long body truncation
    long_body = "a" * (MAX_LENGTH_STATE_STATE + 50)
    provider.data = {
        "body": long_body,
        "title": "Test Title",
        "type": "note",
    }

    sensor.async_update_callback()

    # Verify truncation
    assert len(sensor._attr_native_value) == MAX_LENGTH_STATE_STATE
    assert sensor._attr_native_value.endswith("...")
    assert sensor._attr_native_value.startswith("a")
    assert sensor._attr_extra_state_attributes["body"] == long_body

    # Test normal length body
    normal_body = "This is a normal body"
    provider.data = {
        "body": normal_body,
        "title": "Test Title",
        "type": "note",
    }

    sensor.async_update_callback()

    # Verify no truncation
    assert sensor._attr_native_value == normal_body
    assert len(sensor._attr_native_value) < MAX_LENGTH_STATE_STATE
    assert sensor._attr_extra_state_attributes["body"] == normal_body

    # Test exactly max length
    exact_body = "a" * MAX_LENGTH_STATE_STATE
    provider.data = {
        "body": exact_body,
        "title": "Test Title",
        "type": "note",
    }

    sensor.async_update_callback()

    # Verify no truncation at the limit
    assert sensor._attr_native_value == exact_body
    assert len(sensor._attr_native_value) == MAX_LENGTH_STATE_STATE
    assert sensor._attr_extra_state_attributes["body"] == exact_body


def test_sensor_truncation_title_sensor() -> None:
    """Test sensor truncation logic on title sensor."""
    provider = _create_mock_provider()
    sensor = _create_test_sensor(provider, "title")

    # Test long title truncation
    long_title = "Title " + "x" * (MAX_LENGTH_STATE_STATE)
    provider.data = {
        "body": "Test body",
        "title": long_title,
        "type": "note",
    }

    sensor.async_update_callback()

    # Verify truncation
    assert len(sensor._attr_native_value) == MAX_LENGTH_STATE_STATE
    assert sensor._attr_native_value.endswith("...")
    assert sensor._attr_native_value.startswith("Title")
    assert sensor._attr_extra_state_attributes["title"] == long_title


def test_sensor_truncation_non_string_handling() -> None:
    """Test that non-string values are handled correctly."""
    provider = _create_mock_provider()
    sensor = _create_test_sensor(provider, "body")

    # Test with None value
    provider.data = {
        "body": None,
        "title": "Test Title",
        "type": "note",
    }

    sensor.async_update_callback()
    assert sensor._attr_native_value is None

    # Test with integer value (would be converted to string by Home Assistant)
    provider.data = {
        "body": 12345,
        "title": "Test Title",
        "type": "note",
    }

    sensor.async_update_callback()
    assert sensor._attr_native_value == 12345  # Not truncated since it's not a string

    # Test with missing key
    provider.data = {
        "title": "Test Title",
        "type": "note",
    }

    # This should not raise an exception
    sensor.async_update_callback()
