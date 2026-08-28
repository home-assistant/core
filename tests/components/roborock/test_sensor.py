"""Test Roborock Sensors."""

from typing import Any

import pytest
from roborock.exceptions import RoborockException
from roborock.roborock_message import RoborockDyadDataProtocol
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
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


def setup_coordinator_side_effect(
    fake_devices: list[FakeDevice], side_effect: Any
) -> None:
    """Set the query/refresh side effect on all fake devices to simulate failure or delay."""
    for device in fake_devices:
        if device.v1_properties is not None:
            device.v1_properties.status.refresh.side_effect = side_effect
        if device.dyad is not None:
            device.dyad.query_values.side_effect = side_effect
        if device.zeo is not None:
            device.zeo.query_values.side_effect = side_effect
        if device.b01_q10_properties is not None:
            device.b01_q10_properties.refresh.side_effect = side_effect
        if device.b01_q7_properties is not None:
            device.b01_q7_properties.query_values.side_effect = side_effect


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (RoborockException("Simulated failure"), STATE_UNAVAILABLE),
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


async def test_dyad_push_updates_state(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_devices: list[FakeDevice],
) -> None:
    """Test an unsolicited device push updates state without waiting for a poll."""
    dyad = next(device.dyad for device in fake_devices if device.dyad is not None)
    assert hass.states.get("sensor.dyad_pro_battery").state == "100"
    assert hass.states.get("sensor.dyad_pro_status").state == "drying"

    push_listener = dyad.add_listener.call_args[0][0]
    push_listener({RoborockDyadDataProtocol.POWER: 50})
    await hass.async_block_till_done()

    assert hass.states.get("sensor.dyad_pro_battery").state == "50"
    assert hass.states.get("sensor.dyad_pro_status").state == "drying"


async def test_dyad_push_unsubscribed_on_unload(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_devices: list[FakeDevice],
) -> None:
    """Test the push listener is unsubscribed when the config entry unloads."""
    dyad = next(device.dyad for device in fake_devices if device.dyad is not None)
    unsub = dyad.add_listener.return_value

    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()

    unsub.assert_called_once()
