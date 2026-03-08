"""Test different accessory types: Switches."""

from datetime import timedelta

from freezegun import freeze_time
import pytest

from homeassistant.components.homekit.const import (
    ATTR_VALUE,
    CHAR_CONFIGURED_NAME,
    CHAR_OUTLET_IN_USE,
    SERV_OUTLET,
    TYPE_FAUCET,
    TYPE_SHOWER,
    TYPE_SPRINKLER,
    TYPE_VALVE,
)
from homeassistant.components.homekit.type_switches import (
    LawnMower,
    Outlet,
    PowerStrip,
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
    """Test SetDuration and RemainingDuration characteristic properties from linked entity attributes."""
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
    """Test remaining duration falls back to default run time only if valve is active."""
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

    # Case 2: Remaining duration should fall back to default duration when accessory is in use
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


async def test_power_strip_accessory(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test PowerStrip accessory with multiple outlets."""
    # Create member switch entities
    switch_entity_ids = [
        "switch.outlet_1",
        "switch.outlet_2",
        "switch.outlet_3",
        "switch.outlet_4",
        "switch.outlet_5",
    ]

    # Set up member switches
    for entity_id in switch_entity_ids:
        hass.states.async_set(
            entity_id,
            STATE_OFF,
            {"friendly_name": f"Outlet {entity_id.rsplit('_', maxsplit=1)[-1]}"},
        )

    # Create power strip group entity
    power_strip_entity_id = "switch.power_strip"
    hass.states.async_set(
        power_strip_entity_id,
        STATE_OFF,
        {ATTR_ENTITY_ID: switch_entity_ids, "friendly_name": "Power Strip"},
    )
    await hass.async_block_till_done()

    # Create PowerStrip accessory
    acc = PowerStrip(hass, hk_driver, "PowerStrip", power_strip_entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    # Verify accessory setup
    assert acc.aid == 2
    assert acc.category == 7  # CATEGORY_OUTLET
    assert len(acc.outlet_chars) == 5
    assert len(acc.outlet_states) == 5

    # Verify all outlets start as off
    for entity_id in switch_entity_ids:
        assert acc.outlet_chars[entity_id].value is False
        assert acc.outlet_states[entity_id] is False

    # Verify we can get outlet services (excluding accessory info service)
    non_info_services = [
        svc for svc in acc.services if hasattr(svc, "unique_id") and svc.unique_id
    ]
    assert len(non_info_services) == 5
    for entity_id in switch_entity_ids:
        outlet_service = next(
            service
            for service in acc.services
            if hasattr(service, "unique_id") and service.unique_id == entity_id
        )
        assert outlet_service.get_characteristic(CHAR_OUTLET_IN_USE).value is True


async def test_power_strip_individual_outlet_control(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test individual outlet control from HomeKit."""
    switch_entity_ids = ["switch.outlet_1", "switch.outlet_2"]

    # Set up member switches
    for entity_id in switch_entity_ids:
        hass.states.async_set(entity_id, STATE_OFF)

    # Create power strip group
    power_strip_entity_id = "switch.power_strip"
    hass.states.async_set(
        power_strip_entity_id,
        STATE_OFF,
        {ATTR_ENTITY_ID: switch_entity_ids},
    )
    await hass.async_block_till_done()

    acc = PowerStrip(hass, hk_driver, "PowerStrip", power_strip_entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    # Mock switch services
    call_turn_on = async_mock_service(hass, "switch", "turn_on")
    call_turn_off = async_mock_service(hass, "switch", "turn_off")

    # Test turning on outlet 1 from HomeKit
    acc.outlet_chars["switch.outlet_1"].client_update_value(True)
    await hass.async_block_till_done()

    assert len(call_turn_on) == 1
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == "switch.outlet_1"
    assert acc.outlet_states["switch.outlet_1"] is True

    # Test turning off outlet 1 from HomeKit
    acc.outlet_chars["switch.outlet_1"].client_update_value(False)
    await hass.async_block_till_done()

    assert len(call_turn_off) == 1
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == "switch.outlet_1"
    assert acc.outlet_states["switch.outlet_1"] is False

    # Test that outlet 2 is independent
    acc.outlet_chars["switch.outlet_2"].client_update_value(True)
    await hass.async_block_till_done()

    assert len(call_turn_on) == 2
    assert call_turn_on[1].data[ATTR_ENTITY_ID] == "switch.outlet_2"
    assert acc.outlet_states["switch.outlet_2"] is True
    assert acc.outlet_states["switch.outlet_1"] is False  # Still off


async def test_power_strip_state_sync_from_ha(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test state synchronization from Home Assistant to HomeKit."""
    switch_entity_ids = ["switch.outlet_1", "switch.outlet_2"]

    # Set up member switches
    for entity_id in switch_entity_ids:
        hass.states.async_set(entity_id, STATE_OFF)

    # Create power strip group
    power_strip_entity_id = "switch.power_strip"
    hass.states.async_set(
        power_strip_entity_id,
        STATE_OFF,
        {ATTR_ENTITY_ID: switch_entity_ids},
    )
    await hass.async_block_till_done()

    acc = PowerStrip(hass, hk_driver, "PowerStrip", power_strip_entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    # Initially all outlets should be off
    assert acc.outlet_chars["switch.outlet_1"].value is False
    assert acc.outlet_chars["switch.outlet_2"].value is False

    # Turn on outlet 1 in Home Assistant
    hass.states.async_set("switch.outlet_1", STATE_ON)
    hass.states.async_set(
        power_strip_entity_id,
        STATE_OFF,  # Group state can be different
        {ATTR_ENTITY_ID: switch_entity_ids},
    )
    await hass.async_block_till_done()

    # Trigger state update
    state = hass.states.get(power_strip_entity_id)
    acc.async_update_state(state)

    # Verify HomeKit reflects the change
    assert acc.outlet_chars["switch.outlet_1"].value is True
    assert acc.outlet_chars["switch.outlet_2"].value is False
    assert acc.outlet_states["switch.outlet_1"] is True
    assert acc.outlet_states["switch.outlet_2"] is False


async def test_power_strip_invalid_configuration(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test PowerStrip with invalid configuration."""
    # Create power strip without entity_id attribute
    power_strip_entity_id = "switch.power_strip_invalid"
    hass.states.async_set(
        power_strip_entity_id,
        STATE_OFF,
        {},  # No entity_id attribute
    )
    await hass.async_block_till_done()

    acc = PowerStrip(hass, hk_driver, "PowerStrip", power_strip_entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    # Should have no outlet chars or states
    assert len(acc.outlet_chars) == 0
    assert len(acc.outlet_states) == 0


async def test_power_strip_missing_member_entities(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test PowerStrip when some member entities don't exist."""
    switch_entity_ids = ["switch.outlet_1", "switch.nonexistent"]

    # Only create one of the switches
    hass.states.async_set("switch.outlet_1", STATE_OFF)

    # Create power strip group with both entities
    power_strip_entity_id = "switch.power_strip"
    hass.states.async_set(
        power_strip_entity_id,
        STATE_OFF,
        {ATTR_ENTITY_ID: switch_entity_ids},
    )
    await hass.async_block_till_done()

    acc = PowerStrip(hass, hk_driver, "PowerStrip", power_strip_entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    # Should only have outlet for the existing entity
    assert len(acc.outlet_chars) == 1
    assert "switch.outlet_1" in acc.outlet_chars
    assert "switch.nonexistent" not in acc.outlet_chars


async def test_power_strip_state_sync_missing_member_entity(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test PowerStrip state update when a known member entity disappears."""
    switch_entity_ids = ["switch.outlet_1", "switch.outlet_2"]

    for entity_id in switch_entity_ids:
        hass.states.async_set(entity_id, STATE_OFF)

    power_strip_entity_id = "switch.power_strip"
    hass.states.async_set(
        power_strip_entity_id,
        STATE_OFF,
        {ATTR_ENTITY_ID: switch_entity_ids},
    )
    await hass.async_block_till_done()

    acc = PowerStrip(hass, hk_driver, "PowerStrip", power_strip_entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    hass.states.async_remove("switch.outlet_2")
    hass.states.async_set("switch.outlet_1", STATE_ON)
    hass.states.async_set(
        power_strip_entity_id,
        STATE_OFF,
        {ATTR_ENTITY_ID: switch_entity_ids},
    )
    await hass.async_block_till_done()

    state = hass.states.get(power_strip_entity_id)
    assert state is not None
    acc.async_update_state(state)

    assert acc.outlet_chars["switch.outlet_1"].value is True
    assert acc.outlet_states["switch.outlet_1"] is True
    assert acc.outlet_chars["switch.outlet_2"].value is False
    assert acc.outlet_states["switch.outlet_2"] is False


async def test_power_strip_primary_service(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test PowerStrip primary service is set correctly."""
    switch_entity_ids = ["switch.outlet_1", "switch.outlet_2"]

    # Set up member switches
    for entity_id in switch_entity_ids:
        hass.states.async_set(entity_id, STATE_OFF)

    # Create power strip group
    power_strip_entity_id = "switch.power_strip"
    hass.states.async_set(
        power_strip_entity_id,
        STATE_OFF,
        {ATTR_ENTITY_ID: switch_entity_ids},
    )
    await hass.async_block_till_done()

    acc = PowerStrip(hass, hk_driver, "PowerStrip", power_strip_entity_id, 2, None)
    acc.run()
    await hass.async_block_till_done()

    # Verify primary service is set by checking that the first outlet service exists
    # and has the correct unique_id
    first_outlet_service = None
    for service in acc.services:
        if hasattr(service, "unique_id") and service.unique_id == "switch.outlet_1":
            first_outlet_service = service
            break

    assert first_outlet_service is not None
    assert first_outlet_service.unique_id == "switch.outlet_1"
