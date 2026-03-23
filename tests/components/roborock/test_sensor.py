"""Test Roborock Sensors."""

import pytest
from roborock.data.b01_q10.b01_q10_code_mappings import B01_Q10_DP
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FakeDevice

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


async def test_q10_vacuum_error_updates_from_push(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_q10_vacuum: FakeDevice,
) -> None:
    """Test Q10 vacuum error sensor updates when status trait pushes updates."""
    entity_id = "sensor.roborock_q10_s5_vacuum_error"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN


    assert fake_q10_vacuum.b01_q10_properties is not None
    # Mutate the fault value, then call refresh to simulate a device push
    fake_q10_vacuum.b01_q10_properties.status.fault = 5
    await fake_q10_vacuum.b01_q10_properties.refresh()
    await hass.async_block_till_done()

    updated_state = hass.states.get(entity_id)
    assert updated_state is not None
    assert updated_state.state == "unknown"
