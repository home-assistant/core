"""Test Roborock Sensors."""

import pytest
from roborock.exceptions import RoborockException
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


async def test_sensors_unavailable(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_devices: list[FakeDevice],
) -> None:
    """Test sensors are still created when the coordinator data is unavailable."""
    for device in fake_devices:
        if device.v1_properties is not None:
            device.v1_properties.status.refresh.side_effect = RoborockException(
                "Simulated V1 failure"
            )
        if device.dyad is not None:
            device.dyad.query_values.side_effect = RoborockException(
                "Simulated Dyad failure"
            )
        if device.zeo is not None:
            device.zeo.query_values.side_effect = RoborockException(
                "Simulated Zeo failure"
            )
        if device.b01_q10_properties is not None:
            device.b01_q10_properties.query_values.side_effect = RoborockException(
                "Simulated Q10 failure"
            )
        if device.b01_q7_properties is not None:
            device.b01_q7_properties.query_values.side_effect = RoborockException(
                "Simulated Q7 failure"
            )

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    # Verify that a sensor from each device type is created but reports STATE_UNAVAILABLE
    for entity_id in (
        "sensor.roborock_s7_maxv_battery",
        "sensor.dyad_pro_battery",
        "sensor.zeo_one_washing_left",
        "sensor.roborock_q10_s5_battery",
        "sensor.roborock_q7_battery",
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE
