"""Test Roborock Switch platform."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
import roborock
from roborock.exceptions import RoborockException
from roborock.roborock_message import RoborockZeoProtocol
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import FakeDevice

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.SWITCH]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switches(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switches and check test values are correctly set."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("switch.roborock_s7_maxv_dock_child_lock"),
        ("switch.roborock_s7_maxv_dock_status_indicator_light"),
        ("switch.roborock_s7_maxv_do_not_disturb"),
    ],
)
async def test_update_success(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_id: str,
) -> None:
    """Test turning switch entities on and off."""
    # The entity fixture in conftest.py starts with the switch on and will
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    # Turn off the switch and verify the entity state is updated properly with
    # the latest information from the trait.
    assert hass.states.get(entity_id) is not None
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_OFF,
        service_data=None,
        blocking=True,
        target={"entity_id": entity_id},
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    # Turn back on and verify the entity state is updated properly with the
    # latest information from the trait
    assert hass.states.get(entity_id) is not None
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_ON,
        service_data=None,
        blocking=True,
        target={"entity_id": entity_id},
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


@pytest.mark.parametrize(
    ("entity_id", "service", "expected_call_fn"),
    [
        (
            "switch.roborock_s7_maxv_dock_status_indicator_light",
            SERVICE_TURN_ON,
            lambda trait: trait.flow_led_status.enable,
        ),
        (
            "switch.roborock_s7_maxv_dock_status_indicator_light",
            SERVICE_TURN_OFF,
            lambda trait: trait.flow_led_status.disable,
        ),
    ],
)
@pytest.mark.parametrize(
    "send_message_exception", [roborock.exceptions.RoborockTimeout]
)
async def test_update_failed(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_id: str,
    service: str,
    fake_vacuum: FakeDevice,
    expected_call_fn: Callable[[Any], Any],
) -> None:
    """Test a failure while updating a switch."""

    expected_call = expected_call_fn(fake_vacuum.v1_properties)
    expected_call.side_effect = roborock.exceptions.RoborockTimeout

    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get(entity_id) is not None
    with (
        pytest.raises(HomeAssistantError, match="Failed to update Roborock options"),
    ):
        await hass.services.async_call(
            "switch",
            service,
            service_data=None,
            blocking=True,
            target={"entity_id": entity_id},
        )

    assert len(expected_call.mock_calls) == 1


@pytest.mark.parametrize(
    ("entity_id"),
    [
        ("switch.zeo_one_sound_setting"),
    ],
)
async def test_a01_switch_success(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_id: str,
    fake_devices: list[FakeDevice],
) -> None:
    """Test turning A01 switch entities on and off."""
    # Get the washing machine (A01) device
    washing_machine = next(
        device
        for device in fake_devices
        if hasattr(device, "zeo") and device.zeo is not None
    )

    # Verify entity exists
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    # Turn on the switch
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_ON,
        service_data=None,
        blocking=True,
        target={"entity_id": entity_id},
    )
    # Verify set_value was called with the correct value (1 for on)
    washing_machine.zeo.set_value.assert_called_with(RoborockZeoProtocol.SOUND_SET, 1)

    # Turn off the switch
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_OFF,
        service_data=None,
        blocking=True,
        target={"entity_id": entity_id},
    )
    # Verify set_value was called with the correct value (0 for off)
    washing_machine.zeo.set_value.assert_called_with(RoborockZeoProtocol.SOUND_SET, 0)


@pytest.mark.parametrize(
    ("entity_id", "service"),
    [
        ("switch.zeo_one_sound_setting", SERVICE_TURN_ON),
        ("switch.zeo_one_sound_setting", SERVICE_TURN_OFF),
    ],
)
async def test_a01_switch_failure(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_id: str,
    service: str,
    fake_devices: list[FakeDevice],
) -> None:
    """Test a failure while updating an A01 switch."""
    # Get the washing machine (A01) device
    washing_machine = next(
        device
        for device in fake_devices
        if hasattr(device, "zeo") and device.zeo is not None
    )
    washing_machine.zeo.set_value.side_effect = roborock.exceptions.RoborockTimeout

    # Ensure that the entity exists
    assert hass.states.get(entity_id) is not None

    with pytest.raises(HomeAssistantError, match="Failed to update Roborock options"):
        await hass.services.async_call(
            "switch",
            service,
            service_data=None,
            blocking=True,
            target={"entity_id": entity_id},
        )

    assert len(washing_machine.zeo.set_value.mock_calls) >= 1


async def test_a01_switch_unknown_state(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_devices: list[FakeDevice],
) -> None:
    """Test A01 switch returns unknown when API omits the protocol key."""
    entity_id = "switch.zeo_one_sound_setting"

    # Verify entity exists with a known state initially
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    # Simulate the API returning data without the SOUND_SET key
    washing_machine = next(
        device
        for device in fake_devices
        if hasattr(device, "zeo") and device.zeo is not None
    )
    incomplete_data = {
        k: v
        for k, v in washing_machine.zeo.query_values.return_value.items()
        if k != RoborockZeoProtocol.SOUND_SET
    }
    washing_machine.zeo.query_values.return_value = incomplete_data

    # Trigger a coordinator refresh
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=61),
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"


async def test_q10_do_not_disturb_switch_success(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_q10_vacuum: FakeDevice,
) -> None:
    """Test turning Q10 Do Not Disturb on and off."""
    entity_id = "switch.roborock_q10_s5_do_not_disturb"

    assert hass.states.get(entity_id) is not None

    await hass.services.async_call(
        "switch",
        SERVICE_TURN_OFF,
        service_data=None,
        blocking=True,
        target={"entity_id": entity_id},
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        "switch",
        SERVICE_TURN_ON,
        service_data=None,
        blocking=True,
        target={"entity_id": entity_id},
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"

    assert fake_q10_vacuum.b01_q10_properties is not None
    assert fake_q10_vacuum.b01_q10_properties.do_not_disturb.enable.call_count == 1
    assert fake_q10_vacuum.b01_q10_properties.do_not_disturb.disable.call_count == 1


async def test_q10_do_not_disturb_switch_failure(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_q10_vacuum: FakeDevice,
) -> None:
    """Test a failure while updating Q10 Do Not Disturb."""
    entity_id = "switch.roborock_q10_s5_do_not_disturb"
    assert fake_q10_vacuum.b01_q10_properties is not None
    fake_q10_vacuum.b01_q10_properties.do_not_disturb.enable.side_effect = (
        roborock.exceptions.RoborockTimeout
    )

    assert hass.states.get(entity_id) is not None

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch",
            SERVICE_TURN_ON,
            service_data=None,
            blocking=True,
            target={"entity_id": entity_id},
        )


async def mock_delay(*args: Any, **kwargs: Any) -> None:
    """Delay the update to simulate before first update completes."""
    await asyncio.sleep(15)


@pytest.mark.parametrize(
    ("side_effect", "expected_state", "expected_v1_state"),
    [
        (RoborockException("Simulated failure"), STATE_UNAVAILABLE, STATE_UNAVAILABLE),
        (mock_delay, STATE_UNKNOWN, "on"),
    ],
)
async def test_switches_coordinator_state(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    fake_devices: list[FakeDevice],
    side_effect: Any,
    expected_state: str,
    expected_v1_state: str,
) -> None:
    """Test switches state based on coordinator update success or delay."""
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

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    # V1 switches (uncoordinated, so they remain available / 'on')
    state = hass.states.get("switch.roborock_s7_maxv_dock_child_lock")
    assert state is not None
    assert state.state == "on"

    # A01 (Dyad/Zeo) switches (coordinated)
    state = hass.states.get("switch.zeo_one_sound_setting")
    assert state is not None
    assert state.state == expected_state
