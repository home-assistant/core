"""Test zha lock."""
from unittest.mock import patch
from homeassistant.const import (
    STATE_LOCKED, STATE_UNLOCKED, STATE_UNAVAILABLE)
from homeassistant.components.lock import DOMAIN
from tests.common import mock_coro
from .common import (
    async_init_zigpy_device, make_attribute, make_entity_id,
    async_enable_traffic)

LOCK_DOOR = 0
UNLOCK_DOOR = 1


async def test_lock(hass, config_entry, zha_gateway):
    """Test zha lock platform."""
    from zigpy.zcl.clusters.closures import DoorLock
    from zigpy.zcl.clusters.general import Basic

    # create zigpy device
    zigpy_device = await async_init_zigpy_device(
        hass, [DoorLock.cluster_id, Basic.cluster_id], [], None, zha_gateway)

    # load up lock domain
    await hass.config_entries.async_forward_entry_setup(
        config_entry, DOMAIN)
    await hass.async_block_till_done()

    cluster = zigpy_device.endpoints.get(1).door_lock
    entity_id = make_entity_id(DOMAIN, zigpy_device, cluster)
    zha_device = zha_gateway.get_device(zigpy_device.ieee)

    # test that the lock was created and that it is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, zha_gateway, [zha_device])

    # test that the state has changed from unavailable to unlocked
    assert hass.states.get(entity_id).state == STATE_UNLOCKED

    # set state to locked
    attr = make_attribute(0, 1)
    cluster.handle_message(False, 1, 0x0a, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_LOCKED

    # set state to unlocked
    attr.value.value = 2
    cluster.handle_message(False, 0, 0x0a, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNLOCKED

    # lock from HA
    await async_lock(hass, cluster, entity_id)

    # unlock from HA
    await async_unlock(hass, cluster, entity_id)


async def async_lock(hass, cluster, entity_id):
    """Test lock functionality from hass."""
    from zigpy.zcl.foundation import Status
    with patch(
            'zigpy.zcl.Cluster.request',
            return_value=mock_coro([Status.SUCCESS, ])):
        # lock via UI
        await hass.services.async_call(DOMAIN, 'lock', {
            'entity_id': entity_id
        }, blocking=True)
        assert cluster.request.call_count == 1
        assert cluster.request.call_args[0][0] is False
        assert cluster.request.call_args[0][1] == LOCK_DOOR


async def async_unlock(hass, cluster, entity_id):
    """Test lock functionality from hass."""
    from zigpy.zcl.foundation import Status
    with patch(
            'zigpy.zcl.Cluster.request',
            return_value=mock_coro([Status.SUCCESS, ])):
        # lock via UI
        await hass.services.async_call(DOMAIN, 'unlock', {
            'entity_id': entity_id
        }, blocking=True)
        assert cluster.request.call_count == 1
        assert cluster.request.call_args[0][0] is False
        assert cluster.request.call_args[0][1] == UNLOCK_DOOR
