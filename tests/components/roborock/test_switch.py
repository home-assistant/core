"""Test Roborock Switch platform."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
import roborock
from roborock import RoborockCommand, RoborockException
from roborock.data import RoborockDockTypeCode, RoborockStateCode
from roborock.device_features import RoborockDockFeatures
from roborock.roborock_message import RoborockDataProtocol, RoborockZeoProtocol
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.const import ATTR_ASSUMED_STATE, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import FakeDevice

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache,
    snapshot_platform,
)


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


DOCK_SWITCH_ENTITY_IDS = {
    "switch.roborock_s7_maxv_dock_dust_emptying",
    "switch.roborock_s7_maxv_dock_mop_washing",
    "switch.roborock_s7_maxv_dock_mop_drying",
}


@pytest.mark.parametrize(
    ("entity_id", "service", "expected_command", "expected_params"),
    [
        (
            "switch.roborock_s7_maxv_dock_dust_emptying",
            SERVICE_TURN_ON,
            RoborockCommand.APP_START_COLLECT_DUST,
            None,
        ),
        (
            "switch.roborock_s7_maxv_dock_dust_emptying",
            SERVICE_TURN_OFF,
            RoborockCommand.APP_STOP_COLLECT_DUST,
            None,
        ),
        (
            "switch.roborock_s7_maxv_dock_mop_washing",
            SERVICE_TURN_ON,
            RoborockCommand.APP_START_WASH,
            None,
        ),
        (
            "switch.roborock_s7_maxv_dock_mop_washing",
            SERVICE_TURN_OFF,
            RoborockCommand.APP_STOP_WASH,
            None,
        ),
        (
            "switch.roborock_s7_maxv_dock_mop_drying",
            SERVICE_TURN_ON,
            RoborockCommand.APP_SET_DRYER_STATUS,
            {"status": 1},
        ),
        (
            "switch.roborock_s7_maxv_dock_mop_drying",
            SERVICE_TURN_OFF,
            RoborockCommand.APP_SET_DRYER_STATUS,
            {"status": 0},
        ),
    ],
)
async def test_dock_switch_commands(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
    entity_id: str,
    service: str,
    expected_command: RoborockCommand,
    expected_params: dict[str, int] | None,
) -> None:
    """Test the dock action switches send the right start and stop commands."""
    assert hass.states.get(entity_id) is not None
    await hass.services.async_call(
        "switch",
        service,
        blocking=True,
        target={"entity_id": entity_id},
    )
    fake_vacuum.v1_properties.command.send.assert_called_once_with(
        expected_command, params=expected_params
    )


@pytest.mark.parametrize(
    ("entity_id", "status_field", "value"),
    [
        pytest.param(
            "switch.roborock_s7_maxv_dock_mop_washing",
            "state",
            RoborockStateCode.washing_the_mop,
            id="wash-from-pushed-state",
        ),
        pytest.param(
            "switch.roborock_s7_maxv_dock_mop_washing",
            "state",
            RoborockStateCode.washing_the_mop_2,
            id="wash-from-alternate-pushed-state",
        ),
        pytest.param(
            "switch.roborock_s7_maxv_dock_mop_drying",
            "dry_status",
            1,
            id="drying-from-pushed-status",
        ),
    ],
)
async def test_dock_switch_reflects_status(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
    entity_id: str,
    status_field: str,
    value: int | RoborockStateCode,
) -> None:
    """Test the dock action switches follow the status reported by the device."""
    assert hass.states.get(entity_id).state == "off"

    # Stop the mock trait from restoring the status template on every refresh.
    fake_vacuum.v1_properties.status.refresh.side_effect = None
    setattr(fake_vacuum.v1_properties.status, status_field, value)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "on"


async def test_dock_switch_follows_pushed_dps(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test a dock switch follows the state pushed over MQTT, without polling.

    Emptying only lasts a few seconds, so the switch relies on the device
    pushing the state rather than on the next refresh.
    """
    entity_id = "switch.roborock_s7_maxv_dock_dust_emptying"
    assert hass.states.get(entity_id).state == "off"

    fake_vacuum.v1_properties.status.update_from_dps(
        {RoborockDataProtocol.STATE: RoborockStateCode.emptying_the_bin}
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "on"

    fake_vacuum.v1_properties.status.update_from_dps(
        {RoborockDataProtocol.STATE: RoborockStateCode.charging}
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "off"


async def test_mop_washing_ignores_going_to_wash_state(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test travelling to the dock to wash does not turn the wash switch on."""
    fake_vacuum.v1_properties.status.refresh.side_effect = None
    fake_vacuum.v1_properties.status.state = RoborockStateCode.going_to_wash_the_mop
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
    await hass.async_block_till_done()

    assert hass.states.get("switch.roborock_s7_maxv_dock_mop_washing").state == "off"


@pytest.mark.parametrize(
    ("entity_id", "service", "expected_command"),
    [
        (
            "switch.roborock_s7_maxv_dock_mop_washing",
            SERVICE_TURN_ON,
            "APP_START_WASH",
        ),
        (
            "switch.roborock_s7_maxv_dock_mop_washing",
            SERVICE_TURN_OFF,
            "APP_STOP_WASH",
        ),
        (
            "switch.roborock_s7_maxv_dock_mop_drying",
            SERVICE_TURN_ON,
            "APP_SET_DRYER_STATUS",
        ),
        (
            "switch.roborock_s7_maxv_dock_mop_drying",
            SERVICE_TURN_OFF,
            "APP_SET_DRYER_STATUS",
        ),
    ],
)
async def test_dock_switch_command_failure(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
    entity_id: str,
    service: str,
    expected_command: str,
) -> None:
    """Test a failing dock command is raised to the user."""
    fake_vacuum.v1_properties.command.send.side_effect = RoborockException

    with pytest.raises(
        HomeAssistantError, match=f"Error while calling {expected_command}"
    ):
        await hass.services.async_call(
            "switch",
            service,
            blocking=True,
            target={"entity_id": entity_id},
        )


@pytest.fixture
def dock_type(request: pytest.FixtureRequest, fake_vacuum: FakeDevice) -> None:
    """Report the parametrized dock type for the fake vacuum."""
    fake_vacuum.v1_properties.device_features.dock_features = (
        RoborockDockFeatures.from_dock_type(request.param)
    )


@pytest.mark.parametrize(
    ("dock_type", "expected_entity_ids"),
    [
        pytest.param(
            RoborockDockTypeCode.o1_dock,
            {"switch.roborock_s7_maxv_dock_dust_emptying"},
            id="collect-only",
        ),
        pytest.param(
            RoborockDockTypeCode.o2_dock,
            {"switch.roborock_s7_maxv_dock_mop_washing"},
            id="wash-only-no-dry",
        ),
        pytest.param(
            RoborockDockTypeCode.o3_dock,
            {
                "switch.roborock_s7_maxv_dock_dust_emptying",
                "switch.roborock_s7_maxv_dock_mop_washing",
            },
            id="collect-and-wash-no-dry",
        ),
        pytest.param(
            RoborockDockTypeCode.shell_e_dock,
            DOCK_SWITCH_ENTITY_IDS,
            id="collect-wash-and-dry",
        ),
        pytest.param(RoborockDockTypeCode.o0_dock, set(), id="no-dock"),
    ],
    indirect=["dock_type"],
)
@pytest.mark.usefixtures("dock_type")
async def test_dock_switches_match_dock_capabilities(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    expected_entity_ids: set[str],
) -> None:
    """Test only the dock action switches the dock supports are created."""
    created = {
        entity_id
        for entity_id in DOCK_SWITCH_ENTITY_IDS
        if hass.states.get(entity_id) is not None
    }
    assert created == expected_entity_ids


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


@pytest.mark.parametrize(
    ("entity_id", "trait_name"),
    [
        ("switch.roborock_q10_s5_do_not_disturb", "do_not_disturb"),
        ("switch.roborock_q10_s5_child_lock", "child_lock"),
        ("switch.roborock_q10_s5_dust_collection", "dust_collection"),
    ],
)
async def test_q10_switch_success(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_q10_vacuum: FakeDevice,
    entity_id: str,
    trait_name: str,
) -> None:
    """Test turning Q10 switch entities on and off."""
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
    trait = getattr(fake_q10_vacuum.b01_q10_properties, trait_name)
    trait.enable.assert_awaited_once()
    trait.disable.assert_awaited_once()


@pytest.mark.parametrize(
    ("entity_id", "trait_name"),
    [
        ("switch.roborock_q10_s5_do_not_disturb", "do_not_disturb"),
        ("switch.roborock_q10_s5_child_lock", "child_lock"),
        ("switch.roborock_q10_s5_dust_collection", "dust_collection"),
    ],
)
async def test_q10_switch_failure(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_q10_vacuum: FakeDevice,
    entity_id: str,
    trait_name: str,
) -> None:
    """Test a failure while updating a Q10 switch."""
    assert fake_q10_vacuum.b01_q10_properties is not None
    trait = getattr(fake_q10_vacuum.b01_q10_properties, trait_name)
    trait.enable.side_effect = roborock.exceptions.RoborockTimeout

    assert hass.states.get(entity_id) is not None

    with pytest.raises(HomeAssistantError, match="Failed to update Roborock options"):
        await hass.services.async_call(
            "switch",
            SERVICE_TURN_ON,
            service_data=None,
            blocking=True,
            target={"entity_id": entity_id},
        )


async def test_q10_button_light_switch(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_q10_vacuum: FakeDevice,
) -> None:
    """Test the Q10 write-only indicator light switch assumes its state."""
    entity_id = "switch.roborock_q10_s5_indicator_light"

    # The device never reports the light state, so it starts unknown
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ASSUMED_STATE) is True

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

    assert fake_q10_vacuum.b01_q10_properties is not None
    fake_q10_vacuum.b01_q10_properties.button_light.enable.assert_awaited_once()
    fake_q10_vacuum.b01_q10_properties.button_light.disable.assert_awaited_once()


async def test_q10_button_light_switch_restore_state(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test the Q10 indicator light restores its assumed state after a restart."""
    entity_id = "switch.roborock_q10_s5_indicator_light"
    mock_restore_cache(hass, (State(entity_id, STATE_ON),))

    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON


async def test_q10_button_light_switch_failure(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_q10_vacuum: FakeDevice,
) -> None:
    """Test the Q10 indicator light keeps its state on a failed command."""
    entity_id = "switch.roborock_q10_s5_indicator_light"
    assert fake_q10_vacuum.b01_q10_properties is not None
    fake_q10_vacuum.b01_q10_properties.button_light.enable.side_effect = (
        roborock.exceptions.RoborockTimeout
    )

    assert hass.states.get(entity_id) is not None

    with pytest.raises(HomeAssistantError, match="Failed to update Roborock options"):
        await hass.services.async_call(
            "switch",
            SERVICE_TURN_ON,
            service_data=None,
            blocking=True,
            target={"entity_id": entity_id},
        )

    # The failed command must not flip the assumed state
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
