"""Tests for the Hidromotic sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set up sensor platform."""
    return [Platform.SENSOR]


async def test_pump_sensor_created(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test that pump sensor is created."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.chi_smart_192_168_1_250_pump_status")
    assert state is not None
    assert state.state == "off"


async def test_pump_sensor_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test pump sensor when pump is on."""
    mock_client.data["pump"]["estado"] = 1
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.chi_smart_192_168_1_250_pump_status")
    assert state is not None
    assert state.state == "on"


async def test_pump_sensor_recovery(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test pump sensor when pump is in recovery mode."""
    mock_client.data["pump"]["estado"] = 11  # PUMP_RECOVERY
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.chi_smart_192_168_1_250_pump_status")
    assert state is not None
    assert state.state == "recovery"


async def test_pump_sensor_no_water(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test pump sensor when pump has no water."""
    mock_client.data["pump"]["estado"] = 5  # PUMP_NO_WATER
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.chi_smart_192_168_1_250_pump_status")
    assert state is not None
    assert state.state == "no_water"


async def test_pump_sensor_extra_attributes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test pump sensor extra state attributes."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.chi_smart_192_168_1_250_pump_status")
    assert state is not None
    assert state.attributes.get("paused") is False
    assert state.attributes.get("pause_type") == "none"


async def test_pump_sensor_external_pause(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test pump sensor when externally paused."""
    mock_client.data["pump"]["pausa_externa"] = 1
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.chi_smart_192_168_1_250_pump_status")
    assert state is not None
    assert state.attributes.get("paused") is True
    assert state.attributes.get("pause_type") == "external"


async def test_pump_sensor_failure_pause(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test pump sensor when paused due to failure."""
    mock_client.data["pump"]["pausa_externa"] = 2
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.chi_smart_192_168_1_250_pump_status")
    assert state is not None
    assert state.attributes.get("paused") is True
    assert state.attributes.get("pause_type") == "failure"


async def test_tank_level_sensor_created(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test that tank level sensor is created."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.chi_smart_192_168_1_250_tank_1_level")
    assert state is not None


async def test_tank_level_sensor_full(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test tank level sensor when tank is full."""
    mock_client.data["tanks"][0]["nivel"] = 0
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.chi_smart_192_168_1_250_tank_1_level")
    assert state is not None
    assert state.state == "full"


async def test_tank_level_sensor_empty(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test tank level sensor when tank is empty."""
    mock_client.data["tanks"][0]["nivel"] = 1
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.chi_smart_192_168_1_250_tank_1_level")
    assert state is not None
    assert state.state == "empty"


async def test_tank_level_sensor_medium(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test tank level sensor when tank is at medium level."""
    mock_client.data["tanks"][0]["nivel"] = 4
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.chi_smart_192_168_1_250_tank_1_level")
    assert state is not None
    assert state.state == "medium"


async def test_tank_level_sensor_sensor_fail(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test tank level sensor when sensor has failed."""
    mock_client.data["tanks"][0]["nivel"] = 2
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.chi_smart_192_168_1_250_tank_1_level")
    assert state is not None
    assert state.state == "sensor_fail"


async def test_tank_level_sensor_level_fail(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test tank level sensor when level measurement has failed."""
    mock_client.data["tanks"][0]["nivel"] = 3
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.chi_smart_192_168_1_250_tank_1_level")
    assert state is not None
    assert state.state == "level_fail"


async def test_pump_sensor_unknown_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test pump sensor with unknown state value."""
    mock_client.data["pump"]["estado"] = 99
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.chi_smart_192_168_1_250_pump_status")
    assert state is not None
    assert state.state == "unknown_99"


async def test_tank_level_sensor_unknown_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
    platforms: list[Platform],
) -> None:
    """Test tank level sensor with unknown state value."""
    mock_client.data["tanks"][0]["nivel"] = 99
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.chi_smart_192_168_1_250_tank_1_level")
    assert state is not None
    assert state.state == "unknown"
