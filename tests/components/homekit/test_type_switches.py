"""Test different accessory types: Switches."""
import pytest

from homeassistant.components.homekit.const import (
    TYPE_FAUCET, TYPE_SHOWER, TYPE_SPRINKLER, TYPE_VALVE)
from homeassistant.components.homekit.type_switches import (
    Outlet, Switch, Valve)
from homeassistant.const import ATTR_ENTITY_ID, CONF_TYPE, STATE_OFF, STATE_ON
from homeassistant.core import split_entity_id

from tests.common import async_mock_service


async def test_outlet_set_state(hass, hk_driver):
    """Test if Outlet accessory and HA are updated accordingly."""
    entity_id = 'switch.outlet_test'

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Outlet(hass, hk_driver, 'Outlet', entity_id, 2, None)
    await hass.async_add_job(acc.run)
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
    call_turn_on = async_mock_service(hass, 'switch', 'turn_on')
    call_turn_off = async_mock_service(hass, 'switch', 'turn_off')

    await hass.async_add_job(acc.char_on.client_update_value, True)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id

    await hass.async_add_job(acc.char_on.client_update_value, False)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id


@pytest.mark.parametrize('entity_id', [
    'automation.test',
    'input_boolean.test',
    'remote.test',
    'script.test',
    'switch.test',
])
async def test_switch_set_state(hass, hk_driver, entity_id):
    """Test if accessory and HA are updated accordingly."""
    domain = split_entity_id(entity_id)[0]

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Switch(hass, hk_driver, 'Switch', entity_id, 2, None)
    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 8  # Switch

    assert acc.char_on.value is False

    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert acc.char_on.value is True

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert acc.char_on.value is False

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, domain, 'turn_on')
    call_turn_off = async_mock_service(hass, domain, 'turn_off')

    await hass.async_add_job(acc.char_on.client_update_value, True)
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id

    await hass.async_add_job(acc.char_on.client_update_value, False)
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id


async def test_valve_set_state(hass, hk_driver):
    """Test if Valve accessory and HA are updated accordingly."""
    entity_id = 'switch.valve_test'

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()

    acc = Valve(hass, hk_driver, 'Valve', entity_id, 2,
                {CONF_TYPE: TYPE_FAUCET})
    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.category == 29  # Faucet
    assert acc.char_valve_type.value == 3  # Water faucet

    acc = Valve(hass, hk_driver, 'Valve', entity_id, 2,
                {CONF_TYPE: TYPE_SHOWER})
    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.category == 30  # Shower
    assert acc.char_valve_type.value == 2  # Shower head

    acc = Valve(hass, hk_driver, 'Valve', entity_id, 2,
                {CONF_TYPE: TYPE_SPRINKLER})
    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()
    assert acc.category == 28  # Sprinkler
    assert acc.char_valve_type.value == 1  # Irrigation

    acc = Valve(hass, hk_driver, 'Valve', entity_id, 2,
                {CONF_TYPE: TYPE_VALVE})
    await hass.async_add_job(acc.run)
    await hass.async_block_till_done()

    assert acc.aid == 2
    assert acc.category == 29  # Faucet

    assert acc.char_active.value is False
    assert acc.char_in_use.value is False
    assert acc.char_valve_type.value == 0  # Generic Valve

    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert acc.char_active.value is True
    assert acc.char_in_use.value is True

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert acc.char_active.value is False
    assert acc.char_in_use.value is False

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, 'switch', 'turn_on')
    call_turn_off = async_mock_service(hass, 'switch', 'turn_off')

    await hass.async_add_job(acc.char_active.client_update_value, True)
    await hass.async_block_till_done()
    assert acc.char_in_use.value is True
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id

    await hass.async_add_job(acc.char_active.client_update_value, False)
    await hass.async_block_till_done()
    assert acc.char_in_use.value is False
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
