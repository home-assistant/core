"""Test Roborock Switch platform."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
import roborock
from roborock.roborock_message import RoborockZeoProtocol
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.const import Platform
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
