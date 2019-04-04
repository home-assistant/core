"""Test zha switch."""
from unittest.mock import call, patch
from homeassistant.components.switch import DOMAIN
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNAVAILABLE
from tests.common import mock_coro
from .common import (
    async_init_zigpy_device, make_attribute, make_entity_id,
    async_test_device_join, async_enable_traffic
)

ON = 1
OFF = 0


async def test_switch(hass, config_entry, zha_gateway):
    """Test zha switch platform."""
    from zigpy.zcl.clusters.general import OnOff, Basic
    from zigpy.zcl.foundation import Status

    # create zigpy device
    zigpy_device = await async_init_zigpy_device(
        hass, [OnOff.cluster_id, Basic.cluster_id], [], None, zha_gateway)

    # load up switch domain
    await hass.config_entries.async_forward_entry_setup(
        config_entry, DOMAIN)
    await hass.async_block_till_done()

    cluster = zigpy_device.endpoints.get(1).on_off
    entity_id = make_entity_id(DOMAIN, zigpy_device, cluster)
    zha_device = zha_gateway.get_device(zigpy_device.ieee)

    # test that the switch was created and that its state is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, zha_gateway, [zha_device])

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

    # turn on from HA
    with patch(
            'zigpy.zcl.Cluster.request',
            return_value=mock_coro([Status.SUCCESS, Status.SUCCESS])):
        # turn on via UI
        await hass.services.async_call(DOMAIN, 'turn_on', {
            'entity_id': entity_id
        }, blocking=True)
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args == call(
            False, ON, (), expect_reply=True, manufacturer=None)

    # turn off from HA
    with patch(
            'zigpy.zcl.Cluster.request',
            return_value=mock_coro([Status.SUCCESS, Status.SUCCESS])):
        # turn off via UI
        await hass.services.async_call(DOMAIN, 'turn_off', {
            'entity_id': entity_id
        }, blocking=True)
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args == call(
            False, OFF, (), expect_reply=True, manufacturer=None)

    # test joining a new switch to the network and HA
    await async_test_device_join(
        hass, zha_gateway, OnOff.cluster_id, DOMAIN)
