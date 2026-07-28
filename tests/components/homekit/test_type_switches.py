"""Test different accessory types: Switches."""

from collections.abc import Callable
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
import pytest

from homeassistant.components.homekit.accessories import HomeDriver
from homeassistant.components.homekit.const import (
    ATTR_VALUE,
    CHAR_ACTIVE,
    CHAR_CONFIGURED_NAME,
    CHAR_IN_USE,
    CHAR_NAME,
    CHAR_REMAINING_DURATION,
    CHAR_STATUS_FAULT,
    SERV_OUTLET,
    TYPE_FAUCET,
    TYPE_IRRIGATION_SYSTEM,
    TYPE_SHOWER,
    TYPE_SPRINKLER,
    TYPE_VALVE,
)
from homeassistant.components.homekit.type_switches import (
    IRRIGATION_DEFAULT_DURATION,
    IRRIGATION_DURATION_MAX,
    IRRIGATION_EXPIRED_CLOSE_MAX_RETRIES,
    IrrigationSystem,
    LawnMower,
    Outlet,
    SelectSwitch,
    Switch,
    Vacuum,
    Valve,
    ValveSwitch,
)
from homeassistant.components.input_number import (
    DOMAIN as INPUT_NUMBER_DOMAIN,
    SERVICE_SET_VALUE as INPUT_NUMBER_SERVICE_SET_VALUE,
)
from homeassistant.components.lawn_mower import (
    DOMAIN as LAWN_MOWER_DOMAIN,
    SERVICE_DOCK,
    SERVICE_START_MOWING,
    LawnMowerActivity,
    LawnMowerEntityFeature,
)
from homeassistant.components.select import ATTR_OPTIONS
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
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
    EVENT_STATE_CHANGED,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SELECT_OPTION,
    STATE_CLOSED,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, HomeAssistant, split_entity_id
from homeassistant.helpers.storage import Store
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
    ["input_select", "select"],
)
async def test_select_switch_with_options_needing_name_cleanup(
    hass: HomeAssistant, hk_driver: HomeDriver, events: list[Event], domain: str
) -> None:
    """Test select options altered by HomeKit name cleanup still sync state."""
    entity_id = f"{domain}.test"
    options = ["always_on", "always on"]

    hass.states.async_set(entity_id, "always_on", {ATTR_OPTIONS: options})
    await hass.async_block_till_done()
    acc = SelectSwitch(hass, hk_driver, "SelectSwitch", entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    outlets = [serv for serv in acc.services if serv.display_name == SERV_OUTLET]
    assert [serv.get_characteristic(CHAR_NAME).value for serv in outlets] == [
        "always on",
        "always on",
    ]
    assert [
        serv.get_characteristic(CHAR_CONFIGURED_NAME).value for serv in outlets
    ] == ["always on", "always on"]

    assert {option: char.value for option, char in acc.select_chars.items()} == {
        "always_on": True,
        "always on": False,
    }

    hass.states.async_set(entity_id, "always on", {ATTR_OPTIONS: options})
    await hass.async_block_till_done()
    assert {option: char.value for option, char in acc.select_chars.items()} == {
        "always_on": False,
        "always on": True,
    }

    call_select_option = async_mock_service(hass, domain, SERVICE_SELECT_OPTION)
    acc.select_chars["always_on"].client_update_value(True)
    await hass.async_block_till_done()

    assert call_select_option
    assert call_select_option[0].data == {
        "entity_id": entity_id,
        "option": "always_on",
    }
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None


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


async def test_valve_switch_with_set_duration_characteristic(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test valve switch with set duration characteristic."""
    entity_id = "switch.sprinkler"

    hass.states.async_set(entity_id, STATE_OFF)
    hass.states.async_set("input_number.valve_duration", "0")
    await hass.async_block_till_done()

    # Mock switch services to prevent errors
    async_mock_service(hass, SWITCH_DOMAIN, SERVICE_TURN_ON)
    async_mock_service(hass, SWITCH_DOMAIN, SERVICE_TURN_OFF)

    acc = ValveSwitch(
        hass,
        hk_driver,
        "Sprinkler",
        entity_id,
        5,
        {"type": "sprinkler", "linked_valve_duration": "input_number.valve_duration"},
    )
    acc.run()
    await hass.async_block_till_done()

    # Assert initial state is synced
    assert acc.get_duration() == 0

    # Simulate setting duration from HomeKit
    call_set_value = async_mock_service(
        hass, INPUT_NUMBER_DOMAIN, INPUT_NUMBER_SERVICE_SET_VALUE
    )
    acc.char_set_duration.client_update_value(300)
    await hass.async_block_till_done()
    assert call_set_value
    assert call_set_value[0].data == {
        "entity_id": "input_number.valve_duration",
        "value": 300,
    }

    # Assert state change in Home Assistant is synced to HomeKit
    hass.states.async_set("input_number.valve_duration", "600")
    await hass.async_block_till_done()
    assert acc.get_duration() == 600

    # Test fallback if no state is set
    hass.states.async_remove("input_number.valve_duration")
    await hass.async_block_till_done()
    assert acc.get_duration() == 0

    # Test remaining duration fallback if no end time is linked
    assert acc.get_remaining_duration() == 0


async def test_valve_switch_with_remaining_duration_characteristic(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test valve switch with remaining duration characteristic."""
    entity_id = "switch.sprinkler"

    hass.states.async_set(entity_id, STATE_OFF)
    hass.states.async_set("sensor.valve_end_time", dt_util.utcnow().isoformat())
    await hass.async_block_till_done()

    # Mock switch services to prevent errors
    async_mock_service(hass, SWITCH_DOMAIN, SERVICE_TURN_ON)
    async_mock_service(hass, SWITCH_DOMAIN, SERVICE_TURN_OFF)

    acc = ValveSwitch(
        hass,
        hk_driver,
        "Sprinkler",
        entity_id,
        5,
        {"type": "sprinkler", "linked_valve_end_time": "sensor.valve_end_time"},
    )
    acc.run()
    await hass.async_block_till_done()

    # Assert initial state is synced
    assert acc.get_remaining_duration() == 0

    # Simulate remaining duration update from Home Assistant
    with freeze_time(dt_util.utcnow()):
        hass.states.async_set(
            "sensor.valve_end_time",
            (dt_util.utcnow() + timedelta(seconds=90)).isoformat(),
        )
        await hass.async_block_till_done()

        # Assert remaining duration is calculated correctly based on end time
        assert acc.get_remaining_duration() == 90

    # Test fallback if no state is set
    hass.states.async_remove("sensor.valve_end_time")
    await hass.async_block_till_done()
    assert acc.get_remaining_duration() == 0

    # Test get duration fallback if no duration is linked
    assert acc.get_duration() == 0


async def test_valve_switch_with_duration_characteristics(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test valve switch with set duration and remaining duration characteristics."""
    entity_id = "switch.sprinkler"

    # Test with duration and end time entities linked
    hass.states.async_set(entity_id, STATE_OFF)
    hass.states.async_set("input_number.valve_duration", "300")
    hass.states.async_set("sensor.valve_end_time", dt_util.utcnow().isoformat())
    await hass.async_block_till_done()

    # Mock switch services to prevent errors
    async_mock_service(hass, SWITCH_DOMAIN, SERVICE_TURN_ON)
    async_mock_service(hass, SWITCH_DOMAIN, SERVICE_TURN_OFF)
    # Mock input_number service for set_duration calls
    call_set_value = async_mock_service(
        hass, INPUT_NUMBER_DOMAIN, INPUT_NUMBER_SERVICE_SET_VALUE
    )

    acc = ValveSwitch(
        hass,
        hk_driver,
        "Sprinkler",
        entity_id,
        5,
        {
            "type": "sprinkler",
            "linked_valve_duration": "input_number.valve_duration",
            "linked_valve_end_time": "sensor.valve_end_time",
        },
    )
    acc.run()
    await hass.async_block_till_done()

    # Test update_duration_chars with both characteristics
    with freeze_time(dt_util.utcnow()):
        hass.states.async_set(
            "sensor.valve_end_time",
            (dt_util.utcnow() + timedelta(seconds=60)).isoformat(),
        )
        hass.states.async_set(entity_id, STATE_OFF)
        await hass.async_block_till_done()
        assert acc.char_set_duration.value == 300
        assert acc.get_remaining_duration() == 60

    # Test get_duration fallback with invalid state
    hass.states.async_set("input_number.valve_duration", "invalid")
    await hass.async_block_till_done()
    assert acc.get_duration() == 0

    # Test get_remaining_duration fallback with invalid state
    hass.states.async_set("sensor.valve_end_time", "invalid")
    await hass.async_block_till_done()
    assert acc.get_remaining_duration() == 0

    # Test get_remaining_duration with end time in the past
    hass.states.async_set(
        "sensor.valve_end_time",
        (dt_util.utcnow() - timedelta(seconds=10)).isoformat(),
    )
    await hass.async_block_till_done()
    assert acc.get_remaining_duration() == 0

    # Test set_duration with negative value
    acc.set_duration(-10)
    await hass.async_block_till_done()
    assert acc.get_duration() == 0
    # Verify the service was called with correct parameters
    assert len(call_set_value) == 1
    assert call_set_value[0].data == {
        "entity_id": "input_number.valve_duration",
        "value": -10,
    }

    # Test set_duration with negative state
    hass.states.async_set("sensor.valve_duration", -10)
    await hass.async_block_till_done()
    assert acc.get_duration() == 0


async def test_valve_with_duration_characteristics(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test valve with set duration and remaining duration characteristics."""
    entity_id = "switch.sprinkler"

    # Test with duration and end time entities linked
    hass.states.async_set(entity_id, STATE_OFF)
    hass.states.async_set("input_number.valve_duration", "900")
    hass.states.async_set("sensor.valve_end_time", dt_util.utcnow().isoformat())
    await hass.async_block_till_done()

    # Using Valve instead of ValveSwitch
    acc = Valve(
        hass,
        hk_driver,
        "Valve",
        entity_id,
        5,
        {
            "linked_valve_duration": "input_number.valve_duration",
            "linked_valve_end_time": "sensor.valve_end_time",
        },
    )
    acc.run()
    await hass.async_block_till_done()

    with freeze_time(dt_util.utcnow()):
        hass.states.async_set(
            "sensor.valve_end_time",
            (dt_util.utcnow() + timedelta(seconds=600)).isoformat(),
        )
        await hass.async_block_till_done()
        assert acc.get_duration() == 900
        assert acc.get_remaining_duration() == 600


async def test_duration_characteristic_properties(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test duration characteristic properties from linked attributes."""
    entity_id = "switch.sprinkler"
    linked_duration_entity = "input_number.valve_duration"
    linked_end_time_entity = "sensor.valve_end_time"

    # Case 1: linked input_number has min, max, step attributes
    hass.states.async_set(entity_id, STATE_OFF)
    hass.states.async_set(
        linked_duration_entity,
        "120",
        {
            "min": 10,
            "max": 900,
            "step": 5,
        },
    )
    hass.states.async_set(linked_end_time_entity, dt_util.utcnow().isoformat())
    await hass.async_block_till_done()

    acc = ValveSwitch(
        hass,
        hk_driver,
        "Sprinkler",
        entity_id,
        5,
        {
            "type": "sprinkler",
            "linked_valve_duration": linked_duration_entity,
            "linked_valve_end_time": linked_end_time_entity,
        },
    )
    acc.run()
    await hass.async_block_till_done()

    set_duration_props = acc.char_set_duration.properties
    assert set_duration_props["minValue"] == 10
    assert set_duration_props["maxValue"] == 900
    assert set_duration_props["minStep"] == 5

    remaining_duration_props = acc.char_remaining_duration.properties
    assert remaining_duration_props["minValue"] == 0
    assert remaining_duration_props["maxValue"] == 900
    assert remaining_duration_props["minStep"] == 1

    # Case 2: linked input_number missing attributes, should use defaults
    hass.states.async_set(
        linked_duration_entity,
        "60",
        {},  # No min, max, step
    )
    await hass.async_block_till_done()

    acc = ValveSwitch(
        hass,
        hk_driver,
        "Sprinkler",
        entity_id,
        6,
        {
            "type": "sprinkler",
            "linked_valve_duration": linked_duration_entity,
            "linked_valve_end_time": linked_end_time_entity,
        },
    )
    acc.run()
    await hass.async_block_till_done()

    set_duration_props = acc.char_set_duration.properties
    assert set_duration_props["minValue"] == 0
    assert set_duration_props["maxValue"] == 3600
    assert set_duration_props["minStep"] == 1

    remaining_duration_props = acc.char_remaining_duration.properties
    assert remaining_duration_props["minValue"] == 0
    assert remaining_duration_props["maxValue"] == 60 * 60 * 48
    assert remaining_duration_props["minStep"] == 1

    # Case 4: linked input_number missing attribute value, should use defaults
    hass.states.async_set(
        linked_duration_entity,
        "60",
        {
            "min": 900,
            "max": None,  # No value
        },
    )
    await hass.async_block_till_done()

    acc = ValveSwitch(
        hass,
        hk_driver,
        "Sprinkler",
        entity_id,
        6,
        {
            "type": "sprinkler",
            "linked_valve_duration": linked_duration_entity,
            "linked_valve_end_time": linked_end_time_entity,
        },
    )
    acc.run()
    await hass.async_block_till_done()

    set_duration_props = acc.char_set_duration.properties
    assert set_duration_props["minValue"] == 900
    assert set_duration_props["maxValue"] == 3600
    assert set_duration_props["minStep"] == 1

    remaining_duration_props = acc.char_remaining_duration.properties
    assert remaining_duration_props["minValue"] == 0
    assert remaining_duration_props["maxValue"] == 60 * 60 * 48
    assert remaining_duration_props["minStep"] == 1

    # Case 3: linked input_number missing state, should use defaults
    hass.states.async_remove(linked_duration_entity)
    await hass.async_block_till_done()

    acc = ValveSwitch(
        hass,
        hk_driver,
        "Sprinkler",
        entity_id,
        7,
        {
            "type": "sprinkler",
            "linked_valve_duration": linked_duration_entity,
            "linked_valve_end_time": linked_end_time_entity,
        },
    )
    acc.run()
    await hass.async_block_till_done()

    set_duration_props = acc.char_set_duration.properties
    assert set_duration_props["minValue"] == 0
    assert set_duration_props["maxValue"] == 3600
    assert set_duration_props["minStep"] == 1

    remaining_duration_props = acc.char_remaining_duration.properties
    assert remaining_duration_props["minValue"] == 0
    assert remaining_duration_props["maxValue"] == 60 * 60 * 48
    assert remaining_duration_props["minStep"] == 1

    # Case 5: Attribute is not valid
    assert acc._get_linked_duration_property("invalid_property", 1000) == 1000


async def test_remaining_duration_characteristic_fallback(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test remaining duration falls back to default only if valve active."""
    entity_id = "switch.sprinkler"

    hass.states.async_set(entity_id, STATE_OFF)
    hass.states.async_set("input_number.valve_duration", "900")
    hass.states.async_set("sensor.valve_end_time", None)
    await hass.async_block_till_done()

    acc = ValveSwitch(
        hass,
        hk_driver,
        "Sprinkler",
        entity_id,
        5,
        {
            "type": "sprinkler",
            "linked_valve_duration": "input_number.valve_duration",
            "linked_valve_end_time": "sensor.valve_end_time",
        },
    )
    acc.run()
    await hass.async_block_till_done()

    # Case 1: Remaining duration should always be 0 when accessory is not in use
    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert acc.char_in_use.value == 0
    assert acc.get_remaining_duration() == 0

    # Case 2: Remaining duration should fall back to default duration when accessory is
    # in use
    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert acc.char_in_use.value == 1
    assert acc.get_remaining_duration() == 900

    # Case 3: Remaining duration calculated from linked end time if state is available
    with freeze_time(dt_util.utcnow()):
        # End time is in the futue and valve is in use
        hass.states.async_set(
            "sensor.valve_end_time",
            (dt_util.utcnow() + timedelta(seconds=3600)).isoformat(),
        )
        await hass.async_block_till_done()
        assert acc.char_in_use.value == 1
        assert acc.get_remaining_duration() == 3600

        # End time is in the futue and valve is not in use
        hass.states.async_set(entity_id, STATE_OFF)
        await hass.async_block_till_done()
        assert acc.char_in_use.value == 0
        assert acc.get_remaining_duration() == 3600

        # End time is in the past and valve is in use, returning 0
        hass.states.async_set(entity_id, STATE_ON)
        hass.states.async_set(
            "sensor.valve_end_time",
            (dt_util.utcnow() - timedelta(seconds=3600)).isoformat(),
        )
        await hass.async_block_till_done()
        assert acc.char_in_use.value == 1
        assert acc.get_remaining_duration() == 0

        # End time is in the past and valve is not in use, returning 0
        hass.states.async_set(entity_id, STATE_OFF)
        await hass.async_block_till_done()
        assert acc.char_in_use.value == 0
        assert acc.get_remaining_duration() == 0


async def test_irrigation_system_reads_valve_duration_attributes(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test IrrigationSystem reads duration/remaining attributes from valve state."""
    hass.states.async_set(
        "valve.front_lawn",
        STATE_OPEN,
        {"duration": 1800, "remaining_duration": 600},
    )
    hass.states.async_set("valve.back_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        9,
        {
            CONF_TYPE: TYPE_IRRIGATION_SYSTEM,
            "linked_irrigation_valves": ["valve.back_lawn"],
        },
    )
    acc.run()
    await hass.async_block_till_done()

    front_chars = acc._valve_chars["valve.front_lawn"]
    assert acc._char_program_mode.value == 0
    assert front_chars[CHAR_IN_USE].value == 1
    assert front_chars["duration"] == 1800
    assert front_chars[CHAR_REMAINING_DURATION].value == 600


async def test_irrigation_system_resyncs_linked_zone_on_service_failure(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test failed linked valve command re-syncs from Home Assistant state."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    hass.states.async_set("valve.back_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        10,
        {
            CONF_TYPE: TYPE_IRRIGATION_SYSTEM,
            "linked_irrigation_valves": ["valve.back_lawn"],
        },
    )
    acc.run()
    await hass.async_block_till_done()

    with patch.object(
        acc, "async_call_service_and_wait", AsyncMock(return_value=False)
    ):
        acc._set_valve_active("valve.back_lawn", 1)
        await hass.async_block_till_done()

    back_chars = acc._valve_chars["valve.back_lawn"]
    assert back_chars[CHAR_ACTIVE].value == 0
    assert back_chars[CHAR_IN_USE].value == 0
    assert back_chars[CHAR_REMAINING_DURATION].value == 0


async def test_irrigation_system_failed_expiry_close_preserves_deadline(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test failed auto-close expiry keeps the persisted deadline for retry."""
    hass.states.async_set("valve.front_lawn", STATE_OPEN)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        10,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    acc._start_local_runtime("valve.front_lawn", 1)
    await hass.async_block_till_done()

    with (
        patch.object(acc, "async_call_service_and_wait", AsyncMock(return_value=False)),
        patch.object(acc, "_sync_valve_chars"),
    ):
        await acc._async_call_local_runtime_close_and_resync("valve.front_lawn")

    assert "valve.front_lawn" in acc._runtime_deadlines


async def test_irrigation_system_preserves_homekit_set_duration_without_device_attr(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test HomeKit-selected duration persists when valve lacks duration attrs."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        11,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    acc._set_valve_duration("valve.front_lawn", 900)
    hass.states.async_set("valve.front_lawn", STATE_OPEN)
    await hass.async_block_till_done()

    front_chars = acc._valve_chars["valve.front_lawn"]
    assert front_chars["duration"] == 900
    assert front_chars[CHAR_REMAINING_DURATION].value >= 899


async def test_irrigation_system_reports_fault_for_unavailable_zone(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test unavailable linked valves are marked unavailable in HomeKit."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    hass.states.async_set("valve.back_lawn", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        11,
        {
            CONF_TYPE: TYPE_IRRIGATION_SYSTEM,
            "linked_irrigation_valves": ["valve.back_lawn"],
        },
    )
    acc.run()
    await hass.async_block_till_done()

    back_chars = acc._valve_chars["valve.back_lawn"]
    assert back_chars[CHAR_ACTIVE].value == 0
    assert back_chars[CHAR_IN_USE].value == 0
    assert back_chars[CHAR_STATUS_FAULT].value == 1
    assert acc._char_system_status_fault.value == 1


async def test_irrigation_system_primary_unavailable_sets_fault(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test primary valve unavailable update sets zone/system status fault."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        12,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    hass.states.async_set("valve.front_lawn", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    front_chars = acc._valve_chars["valve.front_lawn"]
    assert front_chars[CHAR_ACTIVE].value == 0
    assert front_chars[CHAR_IN_USE].value == 0
    assert front_chars[CHAR_STATUS_FAULT].value == 1
    assert acc._char_system_status_fault.value == 1


async def test_irrigation_system_primary_unavailable_keeps_composite_available(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test grouped irrigation stays available when a linked valve is available."""
    hass.states.async_set("valve.front_lawn", STATE_UNAVAILABLE)
    hass.states.async_set("valve.back_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        12,
        {
            CONF_TYPE: TYPE_IRRIGATION_SYSTEM,
            "linked_irrigation_valves": ["valve.back_lawn"],
        },
    )
    acc.run()
    await hass.async_block_till_done()

    assert acc.available is True

    hass.states.async_set("valve.back_lawn", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    assert acc.available is False


async def test_irrigation_system_marks_linked_zone_fault_on_state_remove(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test linked zone state removal marks the zone and system as faulted."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    hass.states.async_set("valve.back_lawn", STATE_OPEN)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        13,
        {
            CONF_TYPE: TYPE_IRRIGATION_SYSTEM,
            "linked_irrigation_valves": ["valve.back_lawn"],
        },
    )
    acc.run()
    await hass.async_block_till_done()

    hass.states.async_remove("valve.back_lawn")
    await hass.async_block_till_done()

    back_chars = acc._valve_chars["valve.back_lawn"]
    assert back_chars[CHAR_ACTIVE].value == 0
    assert back_chars[CHAR_IN_USE].value == 0
    assert back_chars[CHAR_STATUS_FAULT].value == 1
    assert acc._char_system_status_fault.value == 1


async def test_irrigation_system_applies_set_duration_for_auto_close(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test zone auto-closes after HomeKit set duration when no device timing exists."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        14,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    with patch.object(
        acc, "async_call_service_and_wait", AsyncMock(return_value=True)
    ) as service_mock:
        acc._set_valve_duration("valve.front_lawn", 2)
        acc._set_valve_active("valve.front_lawn", 1)
        await hass.async_block_till_done()

        front_chars = acc._valve_chars["valve.front_lawn"]
        assert front_chars[CHAR_REMAINING_DURATION].value == 2

        now = dt_util.utcnow()
        async_fire_time_changed(hass, now + timedelta(seconds=1))
        await hass.async_block_till_done()
        assert front_chars[CHAR_REMAINING_DURATION].value == 1

        async_fire_time_changed(hass, now + timedelta(seconds=3))
        await hass.async_block_till_done()

    assert front_chars[CHAR_IN_USE].value == 0
    assert any(
        args.args[1] == SERVICE_CLOSE_VALVE for args in service_mock.await_args_list
    )


async def test_irrigation_system_zone_active_characteristic_calls_valve_services(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test zone Active characteristic routes open/close valve services."""
    entity_id = "valve.front_lawn"
    hass.states.async_set(entity_id, STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        entity_id,
        26,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    call_open = async_mock_service(hass, "valve", SERVICE_OPEN_VALVE)
    call_close = async_mock_service(hass, "valve", SERVICE_CLOSE_VALVE)

    front_chars = acc._valve_chars[entity_id]
    front_chars[CHAR_ACTIVE].client_update_value(1)
    await hass.async_block_till_done()
    assert call_open
    assert call_open[0].data[ATTR_ENTITY_ID] == entity_id

    front_chars[CHAR_ACTIVE].client_update_value(0)
    await hass.async_block_till_done()
    assert call_close
    assert call_close[0].data[ATTR_ENTITY_ID] == entity_id


async def test_irrigation_system_restores_local_runtime_deadline_on_startup(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test persisted local runtime deadlines are restored on startup."""
    with freeze_time(dt_util.utcnow()):
        now = dt_util.utcnow()
        persisted_end_time = now + timedelta(seconds=5)
        hass.states.async_set("valve.front_lawn", STATE_OPEN)
        await hass.async_block_till_done()

        acc = IrrigationSystem(
            hass,
            hk_driver,
            "Irrigation",
            "valve.front_lawn",
            25,
            {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
        )

        with patch.object(
            acc._runtime_deadline_store,
            "async_load",
            AsyncMock(
                return_value={"valve.front_lawn": persisted_end_time.isoformat()}
            ),
        ):
            acc.run()
            await hass.async_block_till_done()

        front_chars = acc._valve_chars["valve.front_lawn"]
        assert front_chars["close_timer"] is not None
        assert front_chars["update_timer"] is not None
        assert front_chars["end_time"] == persisted_end_time
        acc.async_stop()


async def test_irrigation_system_startup_expired_deadline_kept_on_close_failure(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test startup close failure keeps expired persisted deadline for retry."""
    with freeze_time(dt_util.utcnow()):
        now = dt_util.utcnow()
        expired_end_time = now - timedelta(seconds=1)
        hass.states.async_set("valve.front_lawn", STATE_OPEN)
        await hass.async_block_till_done()

        acc = IrrigationSystem(
            hass,
            hk_driver,
            "Irrigation",
            "valve.front_lawn",
            30,
            {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
        )

        with (
            patch.object(
                acc._runtime_deadline_store,
                "async_load",
                AsyncMock(
                    return_value={"valve.front_lawn": expired_end_time.isoformat()}
                ),
            ),
            patch.object(acc, "_sync_valve_chars"),
            patch.object(
                acc,
                "async_call_service_and_wait",
                AsyncMock(return_value=False),
            ) as service_mock,
        ):
            acc.run()
            await hass.async_block_till_done()

        assert "valve.front_lawn" in acc._runtime_deadlines
        assert any(
            args.args[1] == SERVICE_CLOSE_VALVE for args in service_mock.await_args_list
        )
        acc.async_stop()


async def test_irrigation_system_startup_expired_deadline_cleared_on_close_success(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test startup close success clears expired persisted deadline."""
    with freeze_time(dt_util.utcnow()):
        now = dt_util.utcnow()
        expired_end_time = now - timedelta(seconds=1)
        hass.states.async_set("valve.front_lawn", STATE_OPEN)
        await hass.async_block_till_done()

        acc = IrrigationSystem(
            hass,
            hk_driver,
            "Irrigation",
            "valve.front_lawn",
            31,
            {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
        )

        with (
            patch.object(
                acc._runtime_deadline_store,
                "async_load",
                AsyncMock(
                    return_value={"valve.front_lawn": expired_end_time.isoformat()}
                ),
            ),
            patch.object(
                acc,
                "async_call_service_and_wait",
                AsyncMock(return_value=True),
            ) as service_mock,
        ):
            acc.run()
            await hass.async_block_till_done()

        assert "valve.front_lawn" not in acc._runtime_deadlines
        assert any(
            args.args[1] == SERVICE_CLOSE_VALVE for args in service_mock.await_args_list
        )
        acc.async_stop()


async def test_irrigation_system_expired_deadline_retry_is_rate_limited(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test expired deadline close retries are rate limited between resyncs."""
    with freeze_time(dt_util.utcnow()):
        now = dt_util.utcnow()
        hass.states.async_set("valve.front_lawn", STATE_OPEN)
        await hass.async_block_till_done()

        acc = IrrigationSystem(
            hass,
            hk_driver,
            "Irrigation",
            "valve.front_lawn",
            32,
            {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
        )
        acc.run()
        await hass.async_block_till_done()

        acc._runtime_deadlines_loaded = True
        acc._runtime_deadlines["valve.front_lawn"] = (
            dt_util.utcnow() - timedelta(seconds=1)
        ).isoformat()

        with patch.object(
            acc,
            "async_call_service_and_wait",
            AsyncMock(return_value=False),
        ) as service_mock:
            state = hass.states.get("valve.front_lawn")
            assert state is not None

            acc._sync_valve_chars("valve.front_lawn", state)
            await hass.async_block_till_done()
            assert service_mock.await_count == 0

            async_fire_time_changed(hass, now + timedelta(seconds=1))
            await hass.async_block_till_done()
            assert service_mock.await_count == 1

            async_fire_time_changed(hass, now + timedelta(seconds=2))
            await hass.async_block_till_done()
            assert service_mock.await_count == 1

        acc.async_stop()


async def test_irrigation_system_expired_deadline_retry_stops_at_max_retries(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test expired deadline retries stop once max retries are reached."""
    hass.states.async_set("valve.front_lawn", STATE_OPEN)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        35,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    acc._runtime_deadlines_loaded = True
    acc._runtime_deadlines["valve.front_lawn"] = (
        dt_util.utcnow() - timedelta(seconds=1)
    ).isoformat()
    acc._valve_chars["valve.front_lawn"]["expired_close_retry_count"] = (
        IRRIGATION_EXPIRED_CLOSE_MAX_RETRIES
    )

    with patch.object(
        acc,
        "async_call_service_and_wait",
        AsyncMock(return_value=False),
    ) as service_mock:
        state = hass.states.get("valve.front_lawn")
        assert state is not None
        acc._sync_valve_chars("valve.front_lawn", state)
        await hass.async_block_till_done()

    assert service_mock.await_count == 0
    acc.async_stop()


async def test_irrigation_system_mirrors_runtime_deadline_to_legacy_store(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test local runtime deadlines are mirrored into per-zone legacy storage."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        36,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc._runtime_deadlines_loaded = True

    legacy_key = acc._legacy_runtime_deadline_store("valve.front_lawn").key
    persisted: dict[str, dict[str, str]] = {}
    end_time = dt_util.utcnow() + timedelta(seconds=10)

    async def mock_async_load(self: Store[dict[str, str]]) -> dict[str, str] | None:
        if self.key == legacy_key:
            return None
        return {}

    def mock_async_delay_save(
        self: Store[dict[str, str]],
        save_func: Callable[[], dict[str, str]],
        _delay: int,
    ) -> None:
        persisted[self.key] = save_func()

    with (
        patch.object(Store, "async_load", mock_async_load),
        patch.object(Store, "async_delay_save", mock_async_delay_save),
    ):
        await acc._async_set_runtime_deadline("valve.front_lawn", end_time)

    assert persisted[legacy_key]["valve.front_lawn"] == end_time.isoformat()


async def test_irrigation_system_clears_runtime_deadline_in_legacy_store(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test clearing local runtime also clears per-zone legacy storage."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        37,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc._runtime_deadlines_loaded = True
    acc._runtime_deadlines["valve.front_lawn"] = dt_util.utcnow().isoformat()

    legacy_key = acc._legacy_runtime_deadline_store("valve.front_lawn").key
    persisted: dict[str, dict[str, str]] = {}

    async def mock_async_load(self: Store[dict[str, str]]) -> dict[str, str] | None:
        if self.key == legacy_key:
            return {"valve.front_lawn": "2026-01-01T00:00:00+00:00"}
        return {}

    def mock_async_delay_save(
        self: Store[dict[str, str]],
        save_func: Callable[[], dict[str, str]],
        _delay: int,
    ) -> None:
        persisted[self.key] = save_func()

    with (
        patch.object(Store, "async_load", mock_async_load),
        patch.object(Store, "async_delay_save", mock_async_delay_save),
    ):
        await acc._async_clear_runtime_deadline("valve.front_lawn")

    assert "valve.front_lawn" not in acc._runtime_deadlines
    assert "valve.front_lawn" not in persisted[legacy_key]


async def test_irrigation_system_clear_runtime_deadline_legacy_not_dict(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test clearing runtime skips legacy save when legacy data is not a dict."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        38,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc._runtime_deadlines_loaded = True
    acc._runtime_deadlines["valve.front_lawn"] = dt_util.utcnow().isoformat()

    legacy_key = acc._legacy_runtime_deadline_store("valve.front_lawn").key
    saved_keys: list[str] = []

    async def mock_async_load(self: Store[dict[str, str]]) -> dict[str, str] | None:
        if self.key == legacy_key:
            return None
        return {}

    def mock_async_delay_save(
        self: Store[dict[str, str]],
        _save_func: Callable[[], dict[str, str]],
        _delay: int,
    ) -> None:
        saved_keys.append(self.key)

    with (
        patch.object(Store, "async_load", mock_async_load),
        patch.object(Store, "async_delay_save", mock_async_delay_save),
    ):
        await acc._async_clear_runtime_deadline("valve.front_lawn")

    assert "valve.front_lawn" not in acc._runtime_deadlines
    assert saved_keys.count(legacy_key) == 0


async def test_irrigation_system_clear_runtime_deadline_legacy_missing_entity(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test clearing runtime skips legacy save when entity key is absent."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        39,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc._runtime_deadlines_loaded = True
    acc._runtime_deadlines["valve.front_lawn"] = dt_util.utcnow().isoformat()

    legacy_key = acc._legacy_runtime_deadline_store("valve.front_lawn").key
    saved_keys: list[str] = []

    async def mock_async_load(self: Store[dict[str, str]]) -> dict[str, str] | None:
        if self.key == legacy_key:
            return {"valve.back_lawn": "2026-01-01T00:00:00+00:00"}
        return {}

    def mock_async_delay_save(
        self: Store[dict[str, str]],
        _save_func: Callable[[], dict[str, str]],
        _delay: int,
    ) -> None:
        saved_keys.append(self.key)

    with (
        patch.object(Store, "async_load", mock_async_load),
        patch.object(Store, "async_delay_save", mock_async_delay_save),
    ):
        await acc._async_clear_runtime_deadline("valve.front_lawn")

    assert "valve.front_lawn" not in acc._runtime_deadlines
    assert saved_keys.count(legacy_key) == 0


async def test_irrigation_system_schedule_expired_retry_unknown_entity_noop(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test scheduling an expired retry for unknown entity is a no-op."""
    hass.states.async_set("valve.front_lawn", STATE_OPEN)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        40,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )

    with patch.object(
        acc,
        "_async_call_local_runtime_close_and_resync",
        AsyncMock(),
    ) as close_mock:
        acc._schedule_expired_close_retry("valve.unknown")
        await hass.async_block_till_done()

    assert close_mock.await_count == 0


async def test_irrigation_system_clamps_device_duration_to_characteristic_max(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test device duration attributes are clamped to irrigation max duration."""
    hass.states.async_set(
        "valve.front_lawn",
        STATE_OPEN,
        {"duration": IRRIGATION_DURATION_MAX + 1000},
    )
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        41,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    front_chars = acc._valve_chars["valve.front_lawn"]
    assert front_chars["duration"] == IRRIGATION_DURATION_MAX


async def test_irrigation_system_restore_closed_zone_clears_runtime_deadline(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test startup restore clears persisted deadline for closed valves."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        42,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc._runtime_deadlines_loaded = True
    acc._runtime_deadlines = {"valve.front_lawn": dt_util.utcnow().isoformat()}

    with patch.object(
        acc,
        "_async_clear_runtime_deadline",
        AsyncMock(return_value=None),
    ) as clear_mock:
        await acc._async_restore_local_runtime_deadlines()

    clear_mock.assert_awaited_once_with("valve.front_lawn")


async def test_irrigation_system_legacy_runtime_store_is_cached(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test legacy runtime store helper returns the same Store instance."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        43,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )

    first_store = acc._legacy_runtime_deadline_store("valve.front_lawn")
    second_store = acc._legacy_runtime_deadline_store("valve.front_lawn")

    assert first_store is second_store


async def test_irrigation_system_stop_closes_locally_timed_active_valves(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test async_stop closes valves with active local auto-close timers."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        44,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    with (
        patch.object(
            acc,
            "async_call_service_and_wait",
            AsyncMock(return_value=True),
        ),
        patch.object(
            acc,
            "_async_call_local_runtime_close_and_resync",
            AsyncMock(),
        ) as close_mock,
    ):
        acc._set_valve_duration("valve.front_lawn", 10)
        acc._set_valve_active("valve.front_lawn", 1)
        await hass.async_block_till_done()

        acc.async_stop()
        await hass.async_block_till_done()

    close_mock.assert_awaited_once_with("valve.front_lawn")


async def test_irrigation_system_restores_deadline_after_membership_change(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test per-zone fallback restores deadlines after group membership changes."""
    with freeze_time(dt_util.utcnow()):
        now = dt_util.utcnow()
        persisted_end_time = now + timedelta(seconds=5)
        hass.states.async_set("valve.front_lawn", STATE_OPEN)
        hass.states.async_set("valve.back_lawn", STATE_OPEN)
        hass.states.async_set("valve.side_lawn", STATE_OPEN)
        await hass.async_block_till_done()

        old_group = IrrigationSystem(
            hass,
            hk_driver,
            "Irrigation",
            "valve.front_lawn",
            33,
            {
                CONF_TYPE: TYPE_IRRIGATION_SYSTEM,
                "linked_irrigation_valves": ["valve.back_lawn"],
            },
        )

        new_group = IrrigationSystem(
            hass,
            hk_driver,
            "Irrigation",
            "valve.front_lawn",
            34,
            {
                CONF_TYPE: TYPE_IRRIGATION_SYSTEM,
                "linked_irrigation_valves": ["valve.back_lawn", "valve.side_lawn"],
            },
        )

        stable_key = new_group._runtime_deadline_store.key
        old_legacy_key = old_group._legacy_runtime_deadline_store(
            "valve.front_lawn"
        ).key

        async def mock_async_load(self: Store[dict[str, str]]) -> dict[str, str] | None:
            if self.key == stable_key:
                return None
            if self.key == old_legacy_key:
                return {"valve.front_lawn": persisted_end_time.isoformat()}
            return None

        with patch.object(Store, "async_load", mock_async_load):
            new_group.run()
            await hass.async_block_till_done()

        front_chars = new_group._valve_chars["valve.front_lawn"]
        assert front_chars["close_timer"] is not None
        assert front_chars["update_timer"] is not None
        assert front_chars["end_time"] == persisted_end_time
        new_group.async_stop()


async def test_irrigation_system_storage_key_stable_across_primary_changes(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test irrigation runtime storage key depends on grouped valves, not primary."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    hass.states.async_set("valve.back_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    front_primary = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        25,
        {
            CONF_TYPE: TYPE_IRRIGATION_SYSTEM,
            "linked_irrigation_valves": ["valve.back_lawn"],
        },
    )
    back_primary = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.back_lawn",
        26,
        {
            CONF_TYPE: TYPE_IRRIGATION_SYSTEM,
            "linked_irrigation_valves": ["valve.front_lawn"],
        },
    )

    assert (
        front_primary._runtime_deadline_store.key
        == back_primary._runtime_deadline_store.key
    )


async def test_irrigation_system_migrates_legacy_runtime_deadline_store(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test irrigation runtime deadlines migrate from legacy per-primary storage."""
    with freeze_time(dt_util.utcnow()):
        now = dt_util.utcnow()
        persisted_end_time = now + timedelta(seconds=5)
        hass.states.async_set("valve.front_lawn", STATE_OPEN)
        hass.states.async_set("valve.back_lawn", STATE_OPEN)
        await hass.async_block_till_done()

        acc = IrrigationSystem(
            hass,
            hk_driver,
            "Irrigation",
            "valve.back_lawn",
            27,
            {
                CONF_TYPE: TYPE_IRRIGATION_SYSTEM,
                "linked_irrigation_valves": ["valve.front_lawn"],
            },
        )

        stable_key = acc._runtime_deadline_store.key
        legacy_key = Store(
            hass,
            1,
            f"homekit.irrigation_runtime.{hk_driver.entry_id}.valve.front_lawn",
        ).key

        async def mock_async_load(self: Store[dict[str, str]]) -> dict[str, str] | None:
            if self.key == stable_key:
                return None
            if self.key == legacy_key:
                return {"valve.front_lawn": persisted_end_time.isoformat()}
            return None

        with patch.object(Store, "async_load", mock_async_load):
            acc.run()
            await hass.async_block_till_done()

        front_chars = acc._valve_chars["valve.front_lawn"]
        assert front_chars["close_timer"] is not None
        assert front_chars["update_timer"] is not None
        assert front_chars["end_time"] == persisted_end_time
        acc.async_stop()


async def test_irrigation_system_open_state_sync_does_not_start_auto_close(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test syncing an open valve state does not create local auto-close timers."""
    hass.states.async_set("valve.front_lawn", STATE_OPEN)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        15,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    front_chars = acc._valve_chars["valve.front_lawn"]
    assert front_chars["close_timer"] is None
    assert front_chars["update_timer"] is None
    assert front_chars["end_time"] is None
    assert front_chars[CHAR_REMAINING_DURATION].value == IRRIGATION_DEFAULT_DURATION


async def test_irrigation_system_marks_missing_linked_zone_fault_on_startup(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test missing linked zone state is faulted during startup sync."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        15,
        {
            CONF_TYPE: TYPE_IRRIGATION_SYSTEM,
            "linked_irrigation_valves": ["valve.back_lawn"],
        },
    )
    acc.run()
    await hass.async_block_till_done()

    back_chars = acc._valve_chars["valve.back_lawn"]
    assert back_chars[CHAR_ACTIVE].value == 0
    assert back_chars[CHAR_IN_USE].value == 0
    assert back_chars[CHAR_STATUS_FAULT].value == 1
    assert acc._char_system_status_fault.value == 1


async def test_irrigation_system_deactivates_all_valves(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test IrrigationSystem deactivates all valves when HomeKit sets system active=0."""
    hass.states.async_set("valve.front_lawn", STATE_OPEN)
    hass.states.async_set("valve.back_lawn", STATE_OPEN)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        16,
        {
            CONF_TYPE: TYPE_IRRIGATION_SYSTEM,
            "linked_irrigation_valves": ["valve.back_lawn"],
        },
    )
    acc.run()
    await hass.async_block_till_done()

    with patch.object(
        acc, "async_call_service_and_wait", AsyncMock(return_value=True)
    ) as service_mock:
        acc._set_system_active(0)
        await hass.async_block_till_done()

    close_calls = [
        args
        for args in service_mock.await_args_list
        if args.args[1] == SERVICE_CLOSE_VALVE
    ]
    assert len(close_calls) == 2


async def test_irrigation_system_system_active_set_true_is_noop(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test IrrigationSystem activating system (value=1) is a no-op."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        17,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    with patch.object(
        acc, "async_call_service_and_wait", AsyncMock(return_value=True)
    ) as service_mock:
        acc._set_system_active(1)
        await hass.async_block_till_done()

    assert not service_mock.called


async def test_irrigation_system_linked_zone_fault_on_no_old_state(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test linked zone fault when state event has no old_state or new_state."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    hass.states.async_set("valve.back_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        18,
        {
            CONF_TYPE: TYPE_IRRIGATION_SYSTEM,
            "linked_irrigation_valves": ["valve.back_lawn"],
        },
    )
    acc.run()
    await hass.async_block_till_done()

    event = Event(
        EVENT_STATE_CHANGED,
        {"entity_id": "valve.back_lawn", "old_state": None, "new_state": None},
    )
    acc._async_linked_valve_state_changed(event)
    await hass.async_block_till_done()

    back_chars = acc._valve_chars["valve.back_lawn"]
    assert back_chars[CHAR_STATUS_FAULT].value == 1


async def test_irrigation_system_reads_remaining_via_end_time(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test IrrigationSystem reads remaining duration from end_time attribute."""
    with freeze_time(dt_util.utcnow()):
        future_end = (dt_util.utcnow() + timedelta(seconds=120)).isoformat()
        hass.states.async_set(
            "valve.front_lawn",
            STATE_OPEN,
            {"end_time": future_end},
        )
        await hass.async_block_till_done()

        acc = IrrigationSystem(
            hass,
            hk_driver,
            "Irrigation",
            "valve.front_lawn",
            19,
            {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
        )
        acc.run()
        await hass.async_block_till_done()

        front_chars = acc._valve_chars["valve.front_lawn"]
        assert front_chars[CHAR_REMAINING_DURATION].value == 120


async def test_irrigation_system_closed_state_ignores_stale_remaining_attributes(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test closed valves always report zero remaining duration."""
    hass.states.async_set(
        "valve.front_lawn",
        STATE_CLOSED,
        {
            "remaining_duration": 120,
            "end_time": (dt_util.utcnow() + timedelta(seconds=120)).isoformat(),
        },
    )
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        27,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    front_chars = acc._valve_chars["valve.front_lawn"]
    assert front_chars[CHAR_ACTIVE].value == 0
    assert front_chars[CHAR_IN_USE].value == 0
    assert front_chars[CHAR_REMAINING_DURATION].value == 0


async def test_irrigation_system_ignores_impossible_end_time_date(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test impossible end_time values fall back to local runtime handling."""
    hass.states.async_set(
        "valve.front_lawn",
        STATE_OPEN,
        {"end_time": "2026-02-30T00:00:00"},
    )
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        24,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    front_chars = acc._valve_chars["valve.front_lawn"]
    assert front_chars["close_timer"] is None
    assert front_chars["update_timer"] is None
    assert front_chars["end_time"] is None
    assert front_chars[CHAR_REMAINING_DURATION].value == IRRIGATION_DEFAULT_DURATION


async def test_irrigation_system_ignores_infinite_duration_attribute(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test infinite duration attributes fall back to the default duration."""
    hass.states.async_set(
        "valve.front_lawn",
        STATE_OPEN,
        {"duration": "inf"},
    )
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        28,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    front_chars = acc._valve_chars["valve.front_lawn"]
    assert front_chars["duration"] == IRRIGATION_DEFAULT_DURATION
    assert front_chars[CHAR_REMAINING_DURATION].value == IRRIGATION_DEFAULT_DURATION


async def test_irrigation_system_ignores_infinite_remaining_attribute(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test infinite remaining attributes fall back to local runtime handling."""
    hass.states.async_set(
        "valve.front_lawn",
        STATE_OPEN,
        {"remaining_duration": "inf"},
    )
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        29,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    front_chars = acc._valve_chars["valve.front_lawn"]
    assert front_chars[CHAR_REMAINING_DURATION].value == IRRIGATION_DEFAULT_DURATION


async def test_irrigation_system_end_time_remaining_counts_down_without_state_events(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test end_time remaining duration keeps updating between state updates."""
    with freeze_time(dt_util.utcnow()):
        now = dt_util.utcnow()
        expected_end_time = now + timedelta(seconds=3)
        future_end = expected_end_time.isoformat()
        hass.states.async_set(
            "valve.front_lawn",
            STATE_OPEN,
            {"end_time": future_end},
        )
        await hass.async_block_till_done()

        acc = IrrigationSystem(
            hass,
            hk_driver,
            "Irrigation",
            "valve.front_lawn",
            22,
            {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
        )
        acc.run()
        await hass.async_block_till_done()

        front_chars = acc._valve_chars["valve.front_lawn"]
        assert front_chars[CHAR_REMAINING_DURATION].value == 3
        assert front_chars["close_timer"] is None
        assert front_chars["update_timer"] is not None
        assert front_chars["end_time"] == expected_end_time

        async_fire_time_changed(hass, now + timedelta(seconds=1))
        await hass.async_block_till_done()
        assert front_chars[CHAR_REMAINING_DURATION].value == 2
        assert front_chars["update_timer"] is not None
        assert front_chars["end_time"] == expected_end_time

        async_fire_time_changed(hass, now + timedelta(seconds=2))
        await hass.async_block_till_done()
        assert front_chars[CHAR_REMAINING_DURATION].value == 1
        assert front_chars["update_timer"] is not None
        assert front_chars["end_time"] == expected_end_time

        async_fire_time_changed(hass, now + timedelta(seconds=3))
        await hass.async_block_till_done()
        assert front_chars[CHAR_REMAINING_DURATION].value == 0
        assert front_chars["update_timer"] is None
        assert front_chars["end_time"] == expected_end_time
        acc.async_stop()


async def test_irrigation_system_ignores_invalid_duration_attribute(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test IrrigationSystem falls back to default when duration attribute is invalid."""
    hass.states.async_set(
        "valve.front_lawn",
        STATE_CLOSED,
        {"set_duration": "not-a-number"},
    )
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        20,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    front_chars = acc._valve_chars["valve.front_lawn"]
    assert front_chars["duration"] == IRRIGATION_DEFAULT_DURATION


async def test_irrigation_system_zero_duration_skips_timers(
    hass: HomeAssistant, hk_driver: HomeDriver
) -> None:
    """Test IrrigationSystem skips auto-close timers when duration is zero."""
    hass.states.async_set("valve.front_lawn", STATE_CLOSED)
    await hass.async_block_till_done()

    acc = IrrigationSystem(
        hass,
        hk_driver,
        "Irrigation",
        "valve.front_lawn",
        21,
        {CONF_TYPE: TYPE_IRRIGATION_SYSTEM},
    )
    acc.run()
    await hass.async_block_till_done()

    with patch.object(acc, "async_call_service_and_wait", AsyncMock(return_value=True)):
        acc._set_valve_duration("valve.front_lawn", 0)
        acc._set_valve_active("valve.front_lawn", 1)
        await hass.async_block_till_done()

    front_chars = acc._valve_chars["valve.front_lawn"]
    assert front_chars["close_timer"] is None
    assert front_chars["update_timer"] is None
