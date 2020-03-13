"""Test zha switch."""
from unittest.mock import call, patch

import pytest
import zigpy.zcl.clusters.general as general
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.switch import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE

from .common import (
    async_enable_traffic,
    async_test_rejoin,
    find_entity_id,
    send_attributes_report,
)

from tests.common import mock_coro

ON = 1
OFF = 0


@pytest.fixture
def zigpy_device(zigpy_device_mock):
    """Device tracker zigpy device."""
    endpoints = {
        1: {
            "in_clusters": [general.Basic.cluster_id, general.OnOff.cluster_id],
            "out_clusters": [],
            "device_type": 0,
        }
    }
    return zigpy_device_mock(endpoints)


async def test_switch(hass, zha_device_joined_restored, zigpy_device):
    """Test zha switch platform."""

    zha_device = await zha_device_joined_restored(zigpy_device)
    cluster = zigpy_device.endpoints.get(1).on_off
    entity_id = await find_entity_id(DOMAIN, zha_device, hass)
    assert entity_id is not None

    # test that the switch was created and that its state is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])

    # test that the state has changed from unavailable to off
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on at switch
    await send_attributes_report(hass, cluster, {1: 0, 0: 1, 2: 2})
    assert hass.states.get(entity_id).state == STATE_ON

    # turn off at switch
    await send_attributes_report(hass, cluster, {1: 1, 0: 0, 2: 2})
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on from HA
    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=mock_coro([0x00, zcl_f.Status.SUCCESS]),
    ):
        # turn on via UI
        await hass.services.async_call(
            DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
        )
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args == call(
            False, ON, (), expect_reply=True, manufacturer=None, tsn=None
        )

    # turn off from HA
    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=mock_coro([0x01, zcl_f.Status.SUCCESS]),
    ):
        # turn off via UI
        await hass.services.async_call(
            DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
        )
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args == call(
            False, OFF, (), expect_reply=True, manufacturer=None, tsn=None
        )

    # test joining a new switch to the network and HA
    await async_test_rejoin(hass, zigpy_device, [cluster], (1,))
