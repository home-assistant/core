"""Test zha switch."""
from unittest.mock import call, patch

import zigpy.zcl.clusters.general as general
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.switch import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE

from .common import (
    async_enable_traffic,
    async_init_zigpy_device,
    async_test_device_join,
    find_entity_id,
    make_attribute,
    make_zcl_header,
)

from tests.common import mock_coro

ON = 1
OFF = 0


async def test_switch(hass, config_entry, zha_gateway):
    """Test zha switch platform."""

    # create zigpy device
    zigpy_device = await async_init_zigpy_device(
        hass,
        [general.OnOff.cluster_id, general.Basic.cluster_id],
        [],
        None,
        zha_gateway,
    )

    # load up switch domain
    await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
    await hass.async_block_till_done()

    cluster = zigpy_device.endpoints.get(1).on_off
    zha_device = zha_gateway.get_device(zigpy_device.ieee)
    entity_id = await find_entity_id(DOMAIN, zha_device, hass)
    assert entity_id is not None

    # test that the switch was created and that its state is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, zha_gateway, [zha_device])

    # test that the state has changed from unavailable to off
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on at switch
    attr = make_attribute(0, 1)
    hdr = make_zcl_header(zcl_f.Command.Report_Attributes)
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    # turn off at switch
    attr.value.value = 0
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()
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
            False, ON, (), expect_reply=True, manufacturer=None
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
            False, OFF, (), expect_reply=True, manufacturer=None
        )

    # test joining a new switch to the network and HA
    await async_test_device_join(hass, zha_gateway, general.OnOff.cluster_id, entity_id)
