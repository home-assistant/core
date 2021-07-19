"""Test different accessory types: Switches."""
from datetime import timedelta

import pytest

from homeassistant.components.homekit.const import (
    ATTR_VALUE,
    TYPE_FAUCET,
    TYPE_SHOWER,
    TYPE_SPRINKLER,
    TYPE_VALVE,
)
from homeassistant.components.homekit.type_switches import Outlet, Switch, Vacuum, Valve
from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_RETURN_TO_BASE,
    SERVICE_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_CLEANING,
    STATE_DOCKED,
    SUPPORT_RETURN_HOME,
    SUPPORT_START,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_TYPE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import split_entity_id
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, async_mock_service


async def test_outlet_set_state(hass, hk_driver, events):
    """Test if Outlet accessory and HA are updated accordingly."""
    entity_id = "switch.outlet_test"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Outlet(hass, hk_driver, "Outlet", entity_id, 2, None)
    await acc.run()
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

    await hass.async_add_executor_job(acc.char_on.client_update_value, True)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    await hass.async_add_executor_job(acc.char_on.client_update_value, False)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


@pytest.mark.parametrize(
    "entity_id, attrs",
    [
        ("automation.test", {}),
        ("input_boolean.test", {}),
        ("remote.test", {}),
        ("switch.test", {}),
    ],
)
async def test_switch_set_state(hass, hk_driver, entity_id, attrs, events):
    """Test if accessory and HA are updated accordingly."""
    domain = split_entity_id(entity_id)[0]

    hass.states.async_set(entity_id, None, attrs)
    await hass.async_block_till_done()
    acc = Switch(hass, hk_driver, "Switch", entity_id, 2, None)
    await acc.run()
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

    await hass.async_add_executor_job(acc.char_on.client_update_value, True)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    await hass.async_add_executor_job(acc.char_on.client_update_value, False)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


async def test_valve_set_state(hass, hk_driver, events):
    """Test if Valve accessory and HA are updated accordingly."""
    entity_id = "switch.valve_test"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()

    acc = Valve(hass, hk_driver, "Valve", entity_id, 2, {CONF_TYPE: TYPE_FAUCET})
    await acc.run()
    await hass.async_block_till_done()
    assert acc.category == 29  # Faucet
    assert acc.char_valve_type.value == 3  # Water faucet

    acc = Valve(hass, hk_driver, "Valve", entity_id, 2, {CONF_TYPE: TYPE_SHOWER})
    await acc.run()
    await hass.async_block_till_done()
    assert acc.category == 30  # Shower
    assert acc.char_valve_type.value == 2  # Shower head

    acc = Valve(hass, hk_driver, "Valve", entity_id, 2, {CONF_TYPE: TYPE_SPRINKLER})
    await acc.run()
    await hass.async_block_till_done()
    assert acc.category == 28  # Sprinkler
    assert acc.char_valve_type.value == 1  # Irrigation

    acc = Valve(hass, hk_driver, "Valve", entity_id, 2, {CONF_TYPE: TYPE_VALVE})
    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 2
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
    call_turn_on = async_mock_service(hass, "switch", "turn_on")
    call_turn_off = async_mock_service(hass, "switch", "turn_off")

    await hass.async_add_executor_job(acc.char_active.client_update_value, 1)
    await hass.async_block_till_done()
    assert acc.char_in_use.value == 1
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    await hass.async_add_executor_job(acc.char_active.client_update_value, 0)
    await hass.async_block_till_done()
    assert acc.char_in_use.value == 0
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


async def test_vacuum_set_state_with_returnhome_and_start_support(
    hass, hk_driver, events
):
    """Test if Vacuum accessory and HA are updated accordingly."""
    entity_id = "vacuum.roomba"

    hass.states.async_set(
        entity_id, None, {ATTR_SUPPORTED_FEATURES: SUPPORT_RETURN_HOME | SUPPORT_START}
    )
    await hass.async_block_till_done()

    acc = Vacuum(hass, hk_driver, "Vacuum", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()
    assert acc.aid == 2
    assert acc.category == 8  # Switch

    assert acc.char_on.value == 0

    hass.states.async_set(
        entity_id,
        STATE_CLEANING,
        {ATTR_SUPPORTED_FEATURES: SUPPORT_RETURN_HOME | SUPPORT_START},
    )
    await hass.async_block_till_done()
    assert acc.char_on.value == 1

    hass.states.async_set(
        entity_id,
        STATE_DOCKED,
        {ATTR_SUPPORTED_FEATURES: SUPPORT_RETURN_HOME | SUPPORT_START},
    )
    await hass.async_block_till_done()
    assert acc.char_on.value == 0

    # Set from HomeKit
    call_start = async_mock_service(hass, VACUUM_DOMAIN, SERVICE_START)
    call_return_to_base = async_mock_service(
        hass, VACUUM_DOMAIN, SERVICE_RETURN_TO_BASE
    )

    await hass.async_add_executor_job(acc.char_on.client_update_value, 1)
    await hass.async_block_till_done()
    assert acc.char_on.value == 1
    assert call_start
    assert call_start[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    await hass.async_add_executor_job(acc.char_on.client_update_value, 0)
    await hass.async_block_till_done()
    assert acc.char_on.value == 0
    assert call_return_to_base
    assert call_return_to_base[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


async def test_vacuum_set_state_without_returnhome_and_start_support(
    hass, hk_driver, events
):
    """Test if Vacuum accessory and HA are updated accordingly."""
    entity_id = "vacuum.roomba"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()

    acc = Vacuum(hass, hk_driver, "Vacuum", entity_id, 2, None)
    await acc.run()
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

    await hass.async_add_executor_job(acc.char_on.client_update_value, 1)
    await hass.async_block_till_done()
    assert acc.char_on.value == 1
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    await hass.async_add_executor_job(acc.char_on.client_update_value, 0)
    await hass.async_block_till_done()
    assert acc.char_on.value == 0
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


async def test_reset_switch(hass, hk_driver, events):
    """Test if switch accessory is reset correctly."""
    domain = "scene"
    entity_id = "scene.test"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Switch(hass, hk_driver, "Switch", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.activate_only is True
    assert acc.char_on.value is False

    call_turn_on = async_mock_service(hass, domain, "turn_on")
    call_turn_off = async_mock_service(hass, domain, "turn_off")

    await hass.async_add_executor_job(acc.char_on.client_update_value, True)
    await hass.async_block_till_done()
    assert acc.char_on.value is True
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert acc.char_on.value is False
    assert len(events) == 1
    assert not call_turn_off

    await hass.async_add_executor_job(acc.char_on.client_update_value, False)
    await hass.async_block_till_done()
    assert acc.char_on.value is False
    assert len(events) == 1


async def test_script_switch(hass, hk_driver, events):
    """Test if script switch accessory is reset correctly."""
    domain = "script"
    entity_id = "script.test"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Switch(hass, hk_driver, "Switch", entity_id, 2, None)
    await acc.run()
    await hass.async_block_till_done()

    assert acc.activate_only is True
    assert acc.char_on.value is False

    call_turn_on = async_mock_service(hass, domain, "test")
    call_turn_off = async_mock_service(hass, domain, "turn_off")

    await hass.async_add_executor_job(acc.char_on.client_update_value, True)
    await hass.async_block_till_done()
    assert acc.char_on.value is True
    assert call_turn_on
    assert call_turn_on[0].data == {}
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    future = dt_util.utcnow() + timedelta(seconds=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()
    assert acc.char_on.value is False
    assert len(events) == 1
    assert not call_turn_off

    await hass.async_add_executor_job(acc.char_on.client_update_value, False)
    await hass.async_block_till_done()
    assert acc.char_on.value is False
    assert len(events) == 1
