"""Test zha switch."""
from unittest.mock import patch
from homeassistant.components.zha.core.const import DATA_ZHA
from homeassistant.const import STATE_ON, STATE_OFF
from tests.common import mock_coro
from .common import (
    async_init_zigpy_device, make_attribute, make_entity_id
)

SWITCH = 'switch'
ON = 1
OFF = 0
SUCCESS = 0


async def test_switch(hass, config_entry, zha_gateway):
    """Test zha switch platform."""
    from zigpy.zcl.clusters.general import OnOff

    hass.data[DATA_ZHA][SWITCH] = {}

    # create zigpy device
    zigpy_device = await async_init_zigpy_device(
        [OnOff.cluster_id], [], None, zha_gateway, hass)

    # load up switch domain
    await hass.config_entries.async_forward_entry_setup(
        config_entry, SWITCH)
    await hass.async_block_till_done()

    cluster = zigpy_device.endpoints.get(1).on_off
    entity_id = make_entity_id(SWITCH, zigpy_device, cluster)

    # test that the state has changed from unavailable to off
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on at switch
    attr = make_attribute(0, 1)
    cluster.handle_message(False, 1, 0x0a, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    # turn off at switch
    attr.value.value = 0
    cluster.handle_message(False, 0, 0x0a, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    with patch(
            'zigpy.zcl.Cluster.request',
            return_value=mock_coro([SUCCESS, SUCCESS])):
        # turn on via UI
        await hass.services.async_call(SWITCH, 'turn_on', {
            'entity_id': entity_id
        }, blocking=True)
        cluster.request.assert_called_once_with(
            False, ON, (), expect_reply=True, manufacturer=None)

    with patch(
            'zigpy.zcl.Cluster.request',
            return_value=mock_coro([SUCCESS, SUCCESS])):
        # turn off via UI
        await hass.services.async_call(SWITCH, 'turn_off', {
            'entity_id': entity_id
        }, blocking=True)
        cluster.request.assert_called_once_with(
            False, OFF, (), expect_reply=True, manufacturer=None)
