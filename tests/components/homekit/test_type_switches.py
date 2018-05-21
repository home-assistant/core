"""Test different accessory types: Switches."""
import pytest

from homeassistant.core import split_entity_id
from homeassistant.components.homekit.type_switches import Switch
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON

from tests.common import async_mock_service


@pytest.mark.parametrize('entity_id', [
    'switch.test', 'remote.test', 'input_boolean.test'])
async def test_switch_set_state(hass, entity_id):
    """Test if accessory and HA are updated accordingly."""
    domain = split_entity_id(entity_id)[0]

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Switch(hass, 'Switch', entity_id, 2, None)
    await hass.async_add_job(acc.run)

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
