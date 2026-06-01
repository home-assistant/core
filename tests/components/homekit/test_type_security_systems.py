"""Test different accessory types: Security Systems."""

from unittest.mock import patch

from pyhap.loader import get_loader
import pytest

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.components.homekit.const import ATTR_VALUE
from homeassistant.components.homekit.type_security_systems import SecuritySystem
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State

from tests.common import async_mock_service


async def test_switch_set_state(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test if accessory and HA are updated accordingly."""
    code = "1234"
    config = {ATTR_CODE: code}
    entity_id = "alarm_control_panel.test"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = SecuritySystem(hass, hk_driver, "SecuritySystem", entity_id, 2, config)
    acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 11  # AlarmSystem

    assert acc.char_current_state.value == 3
    assert acc.char_target_state.value == 3

    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_AWAY)
    await hass.async_block_till_done()
    assert acc.char_target_state.value == 1
    assert acc.char_current_state.value == 1

    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_HOME)
    await hass.async_block_till_done()
    assert acc.char_target_state.value == 0
    assert acc.char_current_state.value == 0

    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_NIGHT)
    await hass.async_block_till_done()
    assert acc.char_target_state.value == 2
    assert acc.char_current_state.value == 2

    hass.states.async_set(entity_id, AlarmControlPanelState.DISARMED)
    await hass.async_block_till_done()
    assert acc.char_target_state.value == 3
    assert acc.char_current_state.value == 3

    hass.states.async_set(entity_id, AlarmControlPanelState.TRIGGERED)
    await hass.async_block_till_done()
    assert acc.char_target_state.value == 3
    assert acc.char_current_state.value == 4

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_target_state.value == 3
    assert acc.char_current_state.value == 4

    # Set from HomeKit
    call_arm_home = async_mock_service(
        hass, ALARM_CONTROL_PANEL_DOMAIN, "alarm_arm_home"
    )
    call_arm_away = async_mock_service(
        hass, ALARM_CONTROL_PANEL_DOMAIN, "alarm_arm_away"
    )
    call_arm_night = async_mock_service(
        hass, ALARM_CONTROL_PANEL_DOMAIN, "alarm_arm_night"
    )
    call_disarm = async_mock_service(hass, ALARM_CONTROL_PANEL_DOMAIN, "alarm_disarm")

    acc.char_target_state.client_update_value(0)
    await hass.async_block_till_done()
    assert call_arm_home
    assert call_arm_home[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_arm_home[0].data[ATTR_CODE] == code
    assert acc.char_target_state.value == 0
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_target_state.client_update_value(1)
    await hass.async_block_till_done()
    assert call_arm_away
    assert call_arm_away[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_arm_away[0].data[ATTR_CODE] == code
    assert acc.char_target_state.value == 1
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_target_state.client_update_value(2)
    await hass.async_block_till_done()
    assert call_arm_night
    assert call_arm_night[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_arm_night[0].data[ATTR_CODE] == code
    assert acc.char_target_state.value == 2
    assert len(events) == 3
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_target_state.client_update_value(3)
    await hass.async_block_till_done()
    assert call_disarm
    assert call_disarm[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_disarm[0].data[ATTR_CODE] == code
    assert acc.char_target_state.value == 3
    assert len(events) == 4
    assert events[-1].data[ATTR_VALUE] is None


@pytest.mark.parametrize("config", [{}, {ATTR_CODE: None}])
async def test_no_alarm_code(
    hass: HomeAssistant, hk_driver, config, events: list[Event]
) -> None:
    """Test accessory if security_system doesn't require an alarm_code."""
    entity_id = "alarm_control_panel.test"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = SecuritySystem(hass, hk_driver, "SecuritySystem", entity_id, 2, config)

    # Set from HomeKit
    call_arm_home = async_mock_service(
        hass, ALARM_CONTROL_PANEL_DOMAIN, "alarm_arm_home"
    )

    acc.char_target_state.client_update_value(0)
    await hass.async_block_till_done()
    assert call_arm_home
    assert call_arm_home[0].data[ATTR_ENTITY_ID] == entity_id
    assert ATTR_CODE not in call_arm_home[0].data
    assert acc.char_target_state.value == 0
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None


async def test_arming(hass: HomeAssistant, hk_driver) -> None:
    """Test to make sure arming sets the right state."""
    entity_id = "alarm_control_panel.test"

    hass.states.async_set(entity_id, None)

    acc = SecuritySystem(hass, hk_driver, "SecuritySystem", entity_id, 2, {})
    acc.run()
    await hass.async_block_till_done()

    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_AWAY)
    await hass.async_block_till_done()
    assert acc.char_target_state.value == 1
    assert acc.char_current_state.value == 1

    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_HOME)
    await hass.async_block_till_done()
    assert acc.char_target_state.value == 0
    assert acc.char_current_state.value == 0

    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_VACATION)
    await hass.async_block_till_done()
    assert acc.char_target_state.value == 1
    assert acc.char_current_state.value == 1

    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_NIGHT)
    await hass.async_block_till_done()
    assert acc.char_target_state.value == 2
    assert acc.char_current_state.value == 2

    hass.states.async_set(entity_id, AlarmControlPanelState.ARMING)
    await hass.async_block_till_done()
    assert acc.char_target_state.value == 1
    assert acc.char_current_state.value == 3

    hass.states.async_set(entity_id, AlarmControlPanelState.DISARMED)
    await hass.async_block_till_done()
    assert acc.char_target_state.value == 3
    assert acc.char_current_state.value == 3

    hass.states.async_set(entity_id, AlarmControlPanelState.ARMED_AWAY)
    await hass.async_block_till_done()
    assert acc.char_target_state.value == 1
    assert acc.char_current_state.value == 1

    hass.states.async_set(entity_id, AlarmControlPanelState.TRIGGERED)
    await hass.async_block_till_done()
    assert acc.char_target_state.value == 1
    assert acc.char_current_state.value == 4


async def test_supported_states(hass: HomeAssistant, hk_driver) -> None:
    """Test different supported states."""
    code = "1234"
    config = {ATTR_CODE: code}
    entity_id = "alarm_control_panel.test"

    loader = get_loader()
    default_current_states = loader.get_char(
        "SecuritySystemCurrentState"
    ).properties.get("ValidValues")
    default_target_services = loader.get_char(
        "SecuritySystemTargetState"
    ).properties.get("ValidValues")

    # Set up a number of test configuration
    test_configs = [
        {
            "features": AlarmControlPanelEntityFeature.ARM_HOME,
            "current_values": [
                default_current_states["Disarmed"],
                default_current_states["AlarmTriggered"],
                default_current_states["StayArm"],
            ],
            "target_values": [
                default_target_services["Disarm"],
                default_target_services["StayArm"],
            ],
        },
        {
            "features": AlarmControlPanelEntityFeature.ARM_AWAY,
            "current_values": [
                default_current_states["Disarmed"],
                default_current_states["AlarmTriggered"],
                default_current_states["AwayArm"],
            ],
            "target_values": [
                default_target_services["Disarm"],
                default_target_services["AwayArm"],
            ],
        },
        {
            "features": AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY,
            "current_values": [
                default_current_states["Disarmed"],
                default_current_states["AlarmTriggered"],
                default_current_states["StayArm"],
                default_current_states["AwayArm"],
            ],
            "target_values": [
                default_target_services["Disarm"],
                default_target_services["StayArm"],
                default_target_services["AwayArm"],
            ],
        },
        {
            "features": AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.ARM_NIGHT,
            "current_values": [
                default_current_states["Disarmed"],
                default_current_states["AlarmTriggered"],
                default_current_states["StayArm"],
                default_current_states["AwayArm"],
                default_current_states["NightArm"],
            ],
            "target_values": [
                default_target_services["Disarm"],
                default_target_services["StayArm"],
                default_target_services["AwayArm"],
                default_target_services["NightArm"],
            ],
        },
        {
            "features": AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.ARM_NIGHT
            | AlarmControlPanelEntityFeature.TRIGGER,
            "current_values": [
                default_current_states["Disarmed"],
                default_current_states["AlarmTriggered"],
                default_current_states["StayArm"],
                default_current_states["AwayArm"],
                default_current_states["NightArm"],
            ],
            "target_values": [
                default_target_services["Disarm"],
                default_target_services["StayArm"],
                default_target_services["AwayArm"],
                default_target_services["NightArm"],
            ],
        },
    ]

    aid = 1

    for test_config in test_configs:
        attrs = {"supported_features": test_config.get("features")}

        hass.states.async_set(entity_id, None, attributes=attrs)
        await hass.async_block_till_done()

        aid += 1
        acc = SecuritySystem(hass, hk_driver, "SecuritySystem", entity_id, aid, config)
        acc.run()
        await hass.async_block_till_done()

        valid_current_values = acc.char_current_state.properties.get("ValidValues")
        valid_target_values = acc.char_target_state.properties.get("ValidValues")

        for val in valid_current_values.values():
            assert val in test_config.get("current_values")

        for val in valid_target_values.values():
            assert val in test_config.get("target_values")


@pytest.mark.parametrize(
    ("state"),
    [
        (None),
        ("None"),
        (STATE_UNKNOWN),
        (STATE_UNAVAILABLE),
    ],
)
async def test_handle_non_alarm_states(
    hass: HomeAssistant, hk_driver, events: list[Event], state: str
) -> None:
    """Test we can handle states that should not raise."""
    code = "1234"
    config = {ATTR_CODE: code}
    entity_id = "alarm_control_panel.test"

    hass.states.async_set(entity_id, state)
    await hass.async_block_till_done()
    acc = SecuritySystem(hass, hk_driver, "SecuritySystem", entity_id, 2, config)
    acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 11  # AlarmSystem

    assert acc.char_current_state.value == 3
    assert acc.char_target_state.value == 3


async def test_reload_when_supported_features_grew(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test the accessory reloads when supported_features gained a mode.

    The valid values are frozen from supported_features at build time. If a
    feature change slips past the reload guard (e.g. it arrives across an
    unavailable boundary), a state mapping to a now-supported but unregistered
    value would otherwise raise ValueError inside set_value. We reload to
    rebuild the accessory instead.
    """
    entity_id = "alarm_control_panel.test"

    # Build with ARM_AWAY only -> StayArm (0, i.e. armed_home) is not valid.
    away_only = {"supported_features": AlarmControlPanelEntityFeature.ARM_AWAY}
    hass.states.async_set(
        entity_id, AlarmControlPanelState.DISARMED, attributes=away_only
    )
    await hass.async_block_till_done()
    acc = SecuritySystem(hass, hk_driver, "SecuritySystem", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    assert 0 not in acc.char_current_state.properties["ValidValues"].values()

    # A state where supported_features now also advertises ARM_HOME and the
    # state is armed_home -> 0 is now supported but not yet registered. Call
    # async_update_state directly to model the change reaching the accessory
    # without the unavailable -> available transition being caught by the
    # RELOAD_ON_CHANGE_ATTRS guard in async_update_event_state_callback.
    grew = State(
        entity_id,
        AlarmControlPanelState.ARMED_HOME,
        {
            "supported_features": AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.ARM_HOME
        },
    )
    with patch.object(acc, "async_reload") as mock_reload:
        acc.async_update_state(grew)
        await hass.async_block_till_done()

    assert mock_reload.called


async def test_skip_when_state_not_supported(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test an unadvertised state is skipped, not reloaded (no reload loop).

    If the entity reports a state its supported_features never advertised,
    reloading would rebuild the same valid values and loop. We skip instead.
    """
    entity_id = "alarm_control_panel.test"

    # ARM_AWAY only, and it stays that way -> armed_home (0) is never supported.
    away_only = {"supported_features": AlarmControlPanelEntityFeature.ARM_AWAY}
    hass.states.async_set(
        entity_id, AlarmControlPanelState.DISARMED, attributes=away_only
    )
    await hass.async_block_till_done()
    acc = SecuritySystem(hass, hk_driver, "SecuritySystem", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    # armed_home while supported_features still only advertises ARM_AWAY: 0 is
    # neither registered nor currently supported -> skip, don't reload.
    unsupported = State(
        entity_id,
        AlarmControlPanelState.ARMED_HOME,
        {"supported_features": AlarmControlPanelEntityFeature.ARM_AWAY},
    )
    with patch.object(acc, "async_reload") as mock_reload:
        acc.async_update_state(unsupported)
        await hass.async_block_till_done()

    assert not mock_reload.called
    # State left unchanged; no ValueError raised.
    assert 0 not in acc.char_current_state.properties["ValidValues"].values()


async def test_no_reload_when_state_in_valid_values(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test the normal path pushes through without reloading."""
    entity_id = "alarm_control_panel.test"

    attrs = {"supported_features": AlarmControlPanelEntityFeature.ARM_HOME}
    hass.states.async_set(entity_id, AlarmControlPanelState.DISARMED, attributes=attrs)
    await hass.async_block_till_done()
    acc = SecuritySystem(hass, hk_driver, "SecuritySystem", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    with patch.object(acc, "async_reload") as mock_reload:
        hass.states.async_set(
            entity_id, AlarmControlPanelState.ARMED_HOME, attributes=attrs
        )
        await hass.async_block_till_done()

    assert not mock_reload.called
    assert acc.char_current_state.value == 0
