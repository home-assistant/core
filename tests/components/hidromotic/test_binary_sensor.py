"""Tests for the Hidromotic binary sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set up binary_sensor platform."""
    return [Platform.BINARY_SENSOR]


async def test_tank_full_sensor_created(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test that tank full sensor is created."""
    mock_client.data["tanks"][0]["nivel"] = 0  # Full
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.chi_smart_192_168_1_250_tank_1_full")
    assert state is not None


async def test_tank_empty_sensor_created(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test that tank empty sensor is created."""
    mock_client.data["tanks"][0]["nivel"] = 0  # Full (not empty)
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.chi_smart_192_168_1_250_tank_1_empty")
    assert state is not None


async def test_tank_full_sensor_is_on_when_full(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test tank full sensor is on when tank is full."""
    mock_client.data["tanks"][0]["nivel"] = 0  # Full
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.chi_smart_192_168_1_250_tank_1_full")
    assert state is not None
    assert state.state == STATE_ON


async def test_tank_full_sensor_is_off_when_not_full(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test tank full sensor is off when tank is not full."""
    mock_client.data["tanks"][0]["nivel"] = 1  # Empty
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.chi_smart_192_168_1_250_tank_1_full")
    assert state is not None
    assert state.state == STATE_OFF


async def test_tank_empty_sensor_is_on_when_empty(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test tank empty sensor is on when tank is empty."""
    mock_client.data["tanks"][0]["nivel"] = 1  # Empty
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.chi_smart_192_168_1_250_tank_1_empty")
    assert state is not None
    assert state.state == STATE_ON


async def test_tank_empty_sensor_is_off_when_not_empty(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test tank empty sensor is off when tank is not empty."""
    mock_client.data["tanks"][0]["nivel"] = 0  # Full
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.chi_smart_192_168_1_250_tank_1_empty")
    assert state is not None
    assert state.state == STATE_OFF


async def test_tank_sensors_medium_level(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test tank sensors when tank is at medium level."""
    mock_client.data["tanks"][0]["nivel"] = 4  # Medium
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Neither full nor empty
    full_state = hass.states.get("binary_sensor.chi_smart_192_168_1_250_tank_1_full")
    assert full_state is not None
    assert full_state.state == STATE_OFF

    empty_state = hass.states.get("binary_sensor.chi_smart_192_168_1_250_tank_1_empty")
    assert empty_state is not None
    assert empty_state.state == STATE_OFF


async def test_tank_full_sensor_extra_attributes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test tank full sensor extra state attributes."""
    mock_client.data["tanks"][0]["nivel"] = 0  # Full
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.chi_smart_192_168_1_250_tank_1_full")
    assert state is not None
    assert state.attributes.get("level_raw") == 0
    assert state.attributes.get("level") == "full"


async def test_tank_empty_sensor_extra_attributes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test tank empty sensor extra state attributes."""
    mock_client.data["tanks"][0]["nivel"] = 1  # Empty
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.chi_smart_192_168_1_250_tank_1_empty")
    assert state is not None
    assert state.attributes.get("level_raw") == 1
    assert state.attributes.get("level") == "empty"


async def test_tank_sensors_unavailable_on_sensor_fail(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test tank sensors are unavailable when sensor has failed."""
    mock_client.data["tanks"][0]["nivel"] = 2  # Sensor fail
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    full_state = hass.states.get("binary_sensor.chi_smart_192_168_1_250_tank_1_full")
    assert full_state is not None
    assert full_state.state == "unavailable"

    empty_state = hass.states.get("binary_sensor.chi_smart_192_168_1_250_tank_1_empty")
    assert empty_state is not None
    assert empty_state.state == "unavailable"


async def test_tank_sensors_unavailable_on_level_fail(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test tank sensors are unavailable when level measurement has failed."""
    mock_client.data["tanks"][0]["nivel"] = 3  # Level fail
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    full_state = hass.states.get("binary_sensor.chi_smart_192_168_1_250_tank_1_full")
    assert full_state is not None
    assert full_state.state == "unavailable"

    empty_state = hass.states.get("binary_sensor.chi_smart_192_168_1_250_tank_1_empty")
    assert empty_state is not None
    assert empty_state.state == "unavailable"
