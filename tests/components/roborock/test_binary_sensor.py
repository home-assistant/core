"""Test Roborock Binary Sensor."""

import copy
from typing import Any

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
    return [Platform.BINARY_SENSOR]


async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensors and check test values are correctly set."""
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
async def test_binary_sensors_coordinator_state(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_devices: list[FakeDevice],
    side_effect: Any,
    expected_state: str,
) -> None:
    """Test binary sensors state based on coordinator update success or delay."""
    setup_coordinator_side_effect(fake_devices, side_effect)

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    # V1 binary sensors
    state = hass.states.get("binary_sensor.roborock_s7_maxv_mop_attached")
    assert state is not None
    assert state.state == expected_state

    # A01 (Dyad/Zeo) binary sensors
    state = hass.states.get("binary_sensor.zeo_one_detergent")
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize("platforms", [[Platform.BINARY_SENSOR]])
async def test_zeo_request_protocols_filtered_by_schema(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_devices: list[FakeDevice],
) -> None:
    """Test that Zeo request protocols are filtered by the device's supported schema IDs, ensuring correct entities are created."""
    # Find the first Zeo device
    zeo_device_1 = next(
        (device for device in fake_devices if device.zeo is not None),
        None,
    )
    assert zeo_device_1 is not None

    # Create a second Zeo device without softener in its schema
    zeo_device_2 = copy.deepcopy(zeo_device_1)
    zeo_device_2.device_info.duid = "zeo_duid_2"
    zeo_device_2._duid = "zeo_duid_2"
    zeo_device_2.device_info.name = "Zeo Two"
    zeo_device_2._name = "Zeo Two"
    zeo_device_2.device_info.sn = "zeo_sn_2"

    # Exclude softener parameters: 214 (SOFTENER_TYPE) and 227 (SOFTENER_EMPTY)
    zeo_device_2.product.schema = [
        schema
        for schema in zeo_device_2.product.schema
        if schema.id not in ("214", "227")
    ]

    # Add the second device to the list of fake devices
    fake_devices.append(zeo_device_2)

    # Now set up the integration
    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    # Verify that the first Zeo device has both detergent and softener entities
    assert hass.states.get("binary_sensor.zeo_one_detergent") is not None
    assert hass.states.get("binary_sensor.zeo_one_softener") is not None

    # Verify that the second Zeo device has detergent entities but NOT softener entities
    assert hass.states.get("binary_sensor.zeo_two_detergent") is not None
    assert hass.states.get("binary_sensor.zeo_two_softener") is None
