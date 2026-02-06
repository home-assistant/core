"""Tests for the LoJack binary sensor platform."""

from unittest.mock import AsyncMock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .const import TEST_MAKE, TEST_MODEL, TEST_YEAR

from tests.common import MockConfigEntry


async def test_binary_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test binary sensor entities are created."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that binary sensors exist
    assert hass.states.get(
        f"binary_sensor.{TEST_YEAR}_{TEST_MAKE}_{TEST_MODEL}_active".lower()
    )
    assert hass.states.get(
        f"binary_sensor.{TEST_YEAR}_{TEST_MAKE}_{TEST_MODEL}_moving".lower()
    )


async def test_active_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test active (connectivity) sensor."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(
        f"binary_sensor.{TEST_YEAR}_{TEST_MAKE}_{TEST_MODEL}_active".lower()
    )
    assert state is not None
    # Should be ON since we have location data with timestamp
    assert state.state == STATE_ON
    assert state.attributes.get("device_class") == BinarySensorDeviceClass.CONNECTIVITY


async def test_moving_sensor_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test moving sensor when vehicle is moving."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(
        f"binary_sensor.{TEST_YEAR}_{TEST_MAKE}_{TEST_MODEL}_moving".lower()
    )
    assert state is not None
    # TEST_SPEED is 35.0 which is > 0.5 threshold, so should be ON
    assert state.state == STATE_ON
    assert state.attributes.get("device_class") == BinarySensorDeviceClass.MOVING


async def test_moving_sensor_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
    mock_location: AsyncMock,
) -> None:
    """Test moving sensor when vehicle is stationary."""
    # Set speed to 0 (stationary)
    mock_location.speed = 0.0

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(
        f"binary_sensor.{TEST_YEAR}_{TEST_MAKE}_{TEST_MODEL}_moving".lower()
    )
    assert state is not None
    # Speed is 0.0 which is < 0.5 threshold, so should be OFF
    assert state.state == STATE_OFF
