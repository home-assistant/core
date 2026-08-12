"""Test Roborock Binary Sensor."""

import copy
from datetime import timedelta
from typing import Any

import pytest
from roborock.data import RoborockDockTypeCode, RoborockStateCode
from roborock.device_features import RoborockDockFeatures
from roborock.exceptions import RoborockException
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import FakeDevice

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


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


async def test_emptying_dust_bin_follows_pushed_state(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test the emptying sensor follows the pushed vacuum state."""
    entity_id = "binary_sensor.roborock_s7_maxv_dock_emptying_dust_bin"
    assert hass.states.get(entity_id).state == "off"

    # Stop the mock trait from restoring the status template on every refresh.
    fake_vacuum.v1_properties.status.refresh.side_effect = None
    fake_vacuum.v1_properties.status.state = RoborockStateCode.emptying_the_bin
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "on"


@pytest.fixture
def dock_type(request: pytest.FixtureRequest, fake_vacuum: FakeDevice) -> None:
    """Report the parametrized dock type for the fake vacuum."""
    fake_vacuum.v1_properties.device_features.dock_features = (
        RoborockDockFeatures.from_dock_type(request.param)
    )


@pytest.mark.parametrize(
    ("dock_type", "expected"),
    [
        pytest.param(RoborockDockTypeCode.o1_dock, True, id="collect-only"),
        pytest.param(RoborockDockTypeCode.o2_dock, False, id="wash-only"),
        pytest.param(RoborockDockTypeCode.shell_e_dock, True, id="collect-wash-dry"),
        pytest.param(RoborockDockTypeCode.o0_dock, False, id="no-dock"),
    ],
    indirect=["dock_type"],
)
@pytest.mark.usefixtures("dock_type")
async def test_emptying_dust_bin_requires_collectable_dock(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    expected: bool,
) -> None:
    """Test the emptying sensor only exists for a dock that can empty."""
    entity_id = "binary_sensor.roborock_s7_maxv_dock_emptying_dust_bin"
    assert (hass.states.get(entity_id) is not None) == expected

