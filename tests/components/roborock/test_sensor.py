"""Test Roborock Sensors."""

import asyncio
from typing import Any

import pytest
from roborock.exceptions import RoborockException
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FakeDevice, setup_coordinator_side_effect

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.SENSOR]


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensors and check test values are correctly set."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_entry.entry_id)


async def mock_delay(*args: Any, **kwargs: Any) -> None:
    """Delay the update to simulate before first update completes."""
    await asyncio.sleep(15)


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (RoborockException("Simulated failure"), STATE_UNAVAILABLE),
        (mock_delay, STATE_UNKNOWN),
    ],
)
async def test_sensors_coordinator_state(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_devices: list[FakeDevice],
    side_effect: Any,
    expected_state: str,
) -> None:
    """Test sensors state based on coordinator update success or delay."""
    setup_coordinator_side_effect(fake_devices, side_effect)

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    # V1 sensors
    state = hass.states.get("sensor.roborock_s7_maxv_battery")
    assert state is not None
    assert state.state == expected_state

    # A01 (Dyad/Zeo) sensors
    state = hass.states.get("sensor.dyad_pro_battery")
    assert state is not None
    assert state.state == expected_state

    state = hass.states.get("sensor.zeo_one_washing_left")
    assert state is not None
    assert state.state == expected_state

    # B01 Q7 sensors
    state = hass.states.get("sensor.roborock_q7_battery")
    assert state is not None
    assert state.state == expected_state

    # B01 Q10 sensors
    state = hass.states.get("sensor.roborock_q10_s5_battery")
    assert state is not None
    assert state.state == expected_state
