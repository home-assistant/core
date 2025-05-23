"""Test different accessory types: Switches."""

from datetime import timedelta

import pytest

from homeassistant.components.homekit.const import (
    ATTR_VALUE,
    CHAR_CONFIGURED_NAME,
    SERV_OUTLET,
    TYPE_FAUCET,
    TYPE_SHOWER,
    TYPE_SPRINKLER,
    TYPE_VALVE,
)
from homeassistant.components.homekit.type_switches import (
    LawnMower,
    Outlet,
    SelectSwitch,
    Switch,
    Vacuum,
    Valve,
    ValveSwitch,
)
from homeassistant.components.lawn_mower import (
    DOMAIN as LAWN_MOWER_DOMAIN,
    SERVICE_DOCK,
    SERVICE_START_MOWING,
    LawnMowerActivity,
    LawnMowerEntityFeature,
)
from homeassistant.components.select import ATTR_OPTIONS
from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_RETURN_TO_BASE,
    SERVICE_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_TYPE,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SELECT_OPTION,
    STATE_CLOSED,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
)
from homeassistant.core import Event, HomeAssistant, split_entity_id
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed, async_mock_service


async def test_outlet_set_state(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test if Outlet accessory and HA are updated accordingly."""
    entity_id = "switch.outlet_test"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Outlet(hass, hk_driver, "Outlet", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 7  # Outlet

    assert acc.char_on.value is False
    assert acc.char_outlet_in_use.value is True

    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert acc.char_on.value is True

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert acc.char_on.value is False

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, "switch", "turn_on")
    call_turn_off = async_mock_service(hass, "switch", "turn_off")

    acc.char_on.client_update_value(True)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_on.client_update_value(False)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


@pytest.mark.parametrize(
    ("entity_id", "attrs"),
    [
        ("automation.test", {}),
        ("input_boolean.test", {}),
        ("remote.test", {}),
        ("switch.test", {}),
    ],
)
async def test_switch_set_state(
    hass: HomeAssistant, hk_driver, entity_id, attrs, events: list[Event]
) -> None:
    """Test if accessory and HA are updated accordingly."""
    domain = split_entity_id(entity_id)[0]

    hass.states.async_set(entity_id, None, attrs)
    await hass.async_block_till_done()
    acc = Switch(hass, hk_driver, "Switch", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 8  # Switch

    assert acc.activate_only is False
    assert acc.char_on.value is False

    hass.states.async_set(entity_id, STATE_ON, attrs)
    await hass.async_block_till_done()
    assert acc.char_on.value is True

    hass.states.async_set(entity_id, STATE_OFF, attrs)
    await hass.async_block_till_done()
    assert acc.char_on.value is False

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, domain, "turn_on")
    call_turn_off = async_mock_service(hass, domain, "turn_off")

    acc.char_on.client_update_value(True)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_on.client_update_value(False)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


async def test_valve_switch_set_state(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test if Valve accessory and HA are updated accordingly."""
    entity_id = "switch.valve_test"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()

    acc = ValveSwitch(hass, hk_driver, "Valve", entity_id, 2, {CONF_TYPE: TYPE_FAUCET})
    acc.run()
    await hass.async_block_till_done()
    assert acc.category == 29  # Faucet
    assert acc.char_valve_type.value == 3  # Water faucet

    acc = ValveSwitch(hass, hk_driver, "Valve", entity_id, 3, {CONF_TYPE: TYPE_SHOWER})
    acc.run()
    await hass.async_block_till_done()
    assert acc.category == 30  # Shower
    assert acc.char_valve_type.value == 2  # Shower head

    acc = ValveSwitch(
        hass, hk_driver, "Valve", entity_id, 4, {CONF_TYPE: TYPE_SPRINKLER}
    )
    acc.run()
    await hass.async_block_till_done()
    assert acc.category == 28  # Sprinkler
    assert acc.char_valve_type.value == 1  # Irrigation

    acc = ValveSwitch(hass, hk_driver, "Valve", entity_id, 5, {CONF_TYPE: TYPE_VALVE})
    acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 5
    assert acc.category == 29  # Faucet

    assert acc.char_active.value == 0
    assert acc.char_in_use.value == 0
    assert acc.char_valve_type.value == 0  # Generic Valve

    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert acc.char_active.value == 1
    assert acc.char_in_use.value == 1

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert acc.char_active.value == 0
    assert acc.char_in_use.value == 0

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, "switch", SERVICE_TURN_ON)
    call_turn_off = async_mock_service(hass, "switch", SERVICE_TURN_OFF)

    acc.char_active.client_update_value(1)
    await hass.async_block_till_done()
    assert acc.char_in_use.value == 1
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_active.client_update_value(0)
    await hass.async_block_till_done()
    assert acc.char_in_use.value == 0
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


async def test_valve_set_state(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test if Valve accessory and HA are updated accordingly."""
    entity_id = "valve.valve_test"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()

    acc = Valve(hass, hk_driver, "Valve", entity_id, 5, {CONF_TYPE: TYPE_VALVE})
    acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 5
    assert acc.category == 29  # Faucet

    assert acc.char_active.value == 0
    assert acc.char_in_use.value == 0
    assert acc.char_valve_type.value == 0  # Generic Valve

    hass.states.async_set(entity_id, STATE_OPEN)
    await hass.async_block_till_done()
    assert acc.char_active.value == 1
    assert acc.char_in_use.value == 1

    hass.states.async_set(entity_id, STATE_CLOSED)
    await hass.async_block_till_done()
    assert acc.char_active.value == 0
    assert acc.char_in_use.value == 0

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, "valve", SERVICE_OPEN_VALVE)
    call_turn_off = async_mock_service(hass, "valve", SERVICE_CLOSE_VALVE)

    acc.char_active.client_update_value(1)
    await hass.async_block_till_done()
    assert acc.char_in_use.value == 1
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_active.client_update_value(0)
    await hass.async_block_till_done()
    assert acc.char_in_use.value == 0
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


async def test_vacuum_set_state_with_returnhome_and_start_support(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test if Vacuum accessory and HA are updated accordingly."""
    entity_id = "vacuum.roomba"

    hass.states.async_set(
        entity_id,
        None,
        {
            ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.RETURN_HOME
            | VacuumEntityFeature.START
        },
    )
    await hass.async_block_till_done()

    acc = Vacuum(hass, hk_driver, "Vacuum", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()
    assert acc.aid == 2
    assert acc.category == 8  # Switch

    assert acc.char_on.value == 0

    hass.states.async_set(
        entity_id,
        VacuumActivity.CLEANING,
        {
            ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.RETURN_HOME
            | VacuumEntityFeature.START
        },
    )
    await hass.async_block_till_done()
    assert acc.char_on.value == 1

    hass.states.async_set(
        entity_id,
        VacuumActivity.DOCKED,
        {
            ATTR_SUPPORTED_FEATURES: VacuumEntityFeature.RETURN_HOME
            | VacuumEntityFeature.START
        },
    )
    await hass.async_block_till_done()
    assert acc.char_on.value == 0

    # Set from HomeKit
    call_start = async_mock_service(hass, VACUUM_DOMAIN, SERVICE_START)
    call_return_to_base = async_mock_service(
        hass, VACUUM_DOMAIN, SERVICE_RETURN_TO_BASE
    )

    acc.char_on.client_update_value(1)
    await hass.async_block_till_done()
    assert acc.char_on.value == 1
    assert call_start
    assert call_start[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_on.client_update_value(0)
    await hass.async_block_till_done()
    assert acc.char_on.value == 0
    assert call_return_to_base
    assert call_return_to_base[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


async def test_vacuum_set_state_without_returnhome_and_start_support(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test if Vacuum accessory and HA are updated accordingly."""
    entity_id = "vacuum.roomba"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()

    acc = Vacuum(hass, hk_driver, "Vacuum", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()
    assert acc.aid == 2
    assert acc.category == 8  # Switch

    assert acc.char_on.value == 0

    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert acc.char_on.value == 1

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert acc.char_on.value == 0

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, VACUUM_DOMAIN, SERVICE_TURN_ON)
    call_turn_off = async_mock_service(hass, VACUUM_DOMAIN, SERVICE_TURN_OFF)

    acc.char_on.client_update_value(1)
    await hass.async_block_till_done()
    assert acc.char_on.value == 1
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_on.client_update_value(0)
    await hass.async_block_till_done()
    assert acc.char_on.value == 0
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


async def test_lawn_mower_set_state(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test if Lawn mower accessory and HA are updated accordingly."""
    entity_id = "lawn_mower.mower"

    hass.states.async_set(
        entity_id,
        None,
        {
            ATTR_SUPPORTED_FEATURES: LawnMowerEntityFeature.DOCK
            | LawnMowerEntityFeature.START_MOWING
        },
    )
    await hass.async_block_till_done()

    acc = LawnMower(hass, hk_driver, "LawnMower", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()
    assert acc.aid == 2
    assert acc.category == 8  # Switch

    assert acc.char_on.value == 0

    hass.states.async_set(
        entity_id,
        LawnMowerActivity.MOWING,
        {
            ATTR_SUPPORTED_FEATURES: LawnMowerEntityFeature.DOCK
            | LawnMowerEntityFeature.START_MOWING
        },
    )
    await hass.async_block_till_done()
    assert acc.char_on.value == 1

    hass.states.async_set(
        entity_id,
        LawnMowerActivity.DOCKED,
        {
            ATTR_SUPPORTED_FEATURES: LawnMowerEntityFeature.DOCK
            | LawnMowerEntityFeature.START_MOWING
        },
    )
    await hass.async_block_till_done()
    assert acc.char_on.value == 0

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, LAWN_MOWER_DOMAIN, SERVICE_START_MOWING)
    call_turn_off = async_mock_service(hass, LAWN_MOWER_DOMAIN, SERVICE_DOCK)

    acc.char_on.client_update_value(1)
    await hass.async_block_till_done()
    assert acc.char_on.value == 1
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_on.client_update_value(0)
    await hass.async_block_till_done()
    assert acc.char_on.value == 0
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


async def test_reset_switch(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test if switch accessory is reset correctly."""
    domain = "scene"
    entity_id = "scene.test"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Switch(hass, hk_driver, "Switch", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    assert acc.activate_only is True
    assert acc.char_on.value is False

    call_turn_on = async_mock_service(hass, domain, "turn_on")
    call_turn_off = async_mock_service(hass, domain, "turn_off")

    acc.char_on.client_update_value(True)
    await hass.async_block_till_done()
    assert acc.char_on.value is True
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert acc.char_on.value is True

    future = dt_util.utcnow() + timedelta(seconds=10)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert acc.char_on.value is False

    assert len(events) == 1
    assert not call_turn_off

    acc.char_on.client_update_value(False)
    await hass.async_block_till_done()
    assert acc.char_on.value is False
    assert len(events) == 1


async def test_script_switch(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test if script switch accessory is reset correctly."""
    domain = "script"
    entity_id = "script.test"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Switch(hass, hk_driver, "Switch", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    assert acc.activate_only is True
    assert acc.char_on.value is False

    call_turn_on = async_mock_service(hass, domain, "test")
    call_turn_off = async_mock_service(hass, domain, "turn_off")

    acc.char_on.client_update_value(True)
    await hass.async_block_till_done()
    assert acc.char_on.value is True
    assert call_turn_on
    assert call_turn_on[0].data == {}
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert acc.char_on.value is True

    future = dt_util.utcnow() + timedelta(seconds=10)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert acc.char_on.value is False

    assert len(events) == 1
    assert not call_turn_off

    acc.char_on.client_update_value(False)
    await hass.async_block_till_done()
    assert acc.char_on.value is False
    assert len(events) == 1


@pytest.mark.parametrize(
    "domain",
    ["input_select", "select"],
)
async def test_input_select_switch(
    hass: HomeAssistant, hk_driver, events: list[Event], domain
) -> None:
    """Test if select switch accessory is handled correctly."""
    entity_id = f"{domain}.test"

    hass.states.async_set(
        entity_id, "option1", {ATTR_OPTIONS: ["option1", "option2", "option3"]}
    )
    await hass.async_block_till_done()
    acc = SelectSwitch(hass, hk_driver, "SelectSwitch", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    switch_service = acc.get_service(SERV_OUTLET)
    configured_name_char = switch_service.get_characteristic(CHAR_CONFIGURED_NAME)
    assert configured_name_char.value == "option1"

    assert acc.select_chars["option1"].value is True
    assert acc.select_chars["option2"].value is False
    assert acc.select_chars["option3"].value is False

    call_select_option = async_mock_service(hass, domain, SERVICE_SELECT_OPTION)
    acc.select_chars["option2"].client_update_value(True)
    await hass.async_block_till_done()

    assert call_select_option
    assert call_select_option[0].data == {"entity_id": entity_id, "option": "option2"}
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    hass.states.async_set(
        entity_id, "option2", {ATTR_OPTIONS: ["option1", "option2", "option3"]}
    )
    await hass.async_block_till_done()
    assert acc.select_chars["option1"].value is False
    assert acc.select_chars["option2"].value is True
    assert acc.select_chars["option3"].value is False

    hass.states.async_set(
        entity_id, "option3", {ATTR_OPTIONS: ["option1", "option2", "option3"]}
    )
    await hass.async_block_till_done()
    assert acc.select_chars["option1"].value is False
    assert acc.select_chars["option2"].value is False
    assert acc.select_chars["option3"].value is True

    hass.states.async_set(
        entity_id, "invalid", {ATTR_OPTIONS: ["option1", "option2", "option3"]}
    )
    await hass.async_block_till_done()
    assert acc.select_chars["option1"].value is False
    assert acc.select_chars["option2"].value is False
    assert acc.select_chars["option3"].value is False


@pytest.mark.parametrize(
    "domain",
    ["button", "input_button"],
)
async def test_button_switch(
    hass: HomeAssistant, hk_driver, events: list[Event], domain
) -> None:
    """Test switch accessory from a (input) button entity."""
    entity_id = f"{domain}.test"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Switch(hass, hk_driver, "Switch", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    assert acc.activate_only is True
    assert acc.char_on.value is False

    call_press = async_mock_service(hass, domain, "press")

    acc.char_on.client_update_value(True)
    await hass.async_block_till_done()
    assert acc.char_on.value is True
    assert len(call_press) == 1
    assert call_press[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert acc.char_on.value is True

    future = dt_util.utcnow() + timedelta(seconds=10)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert acc.char_on.value is False

    assert len(events) == 1
    assert len(call_press) == 1

    acc.char_on.client_update_value(False)
    await hass.async_block_till_done()
    assert acc.char_on.value is False
    assert len(events) == 1
