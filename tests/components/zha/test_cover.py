"""Test zha cover."""
from unittest.mock import call, patch

import zigpy.types
import zigpy.zcl.clusters.closures as closures
import zigpy.zcl.clusters.general as general
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.cover import DOMAIN
from homeassistant.const import STATE_CLOSED, STATE_OPEN, STATE_UNAVAILABLE

from .common import (
    async_enable_traffic,
    async_init_zigpy_device,
    find_entity_id,
    make_attribute,
    make_zcl_header,
)

from tests.common import mock_coro


async def test_cover(hass, config_entry, zha_gateway):
    """Test zha cover platform."""

    # create zigpy device
    zigpy_device = await async_init_zigpy_device(
        hass,
        [closures.WindowCovering.cluster_id, general.Basic.cluster_id],
        [],
        None,
        zha_gateway,
    )

    # load up cover domain
    await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
    await hass.async_block_till_done()

    cluster = zigpy_device.endpoints.get(1).window_covering
    zha_device = zha_gateway.get_device(zigpy_device.ieee)
    entity_id = await find_entity_id(DOMAIN, zha_device, hass)
    assert entity_id is not None

    # test that the cover was created and that it is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, zha_gateway, [zha_device])

    attr = make_attribute(8, 100)
    hdr = make_zcl_header(zcl_f.Command.Report_Attributes)
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()

    # test that the state has changed from unavailable to off
    assert hass.states.get(entity_id).state == STATE_CLOSED

    # test to see if it opens
    attr = make_attribute(8, 0)
    hdr = make_zcl_header(zcl_f.Command.Report_Attributes)
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OPEN

    # close from UI
    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=mock_coro([0x1, zcl_f.Status.SUCCESS]),
    ):
        await hass.services.async_call(
            DOMAIN, "close_cover", {"entity_id": entity_id}, blocking=True
        )
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args == call(
            False, 0x1, (), expect_reply=True, manufacturer=None
        )

    # open from UI
    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=mock_coro([0x0, zcl_f.Status.SUCCESS]),
    ):
        await hass.services.async_call(
            DOMAIN, "open_cover", {"entity_id": entity_id}, blocking=True
        )
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args == call(
            False, 0x0, (), expect_reply=True, manufacturer=None
        )

    # set position UI
    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=mock_coro([0x5, zcl_f.Status.SUCCESS]),
    ):
        await hass.services.async_call(
            DOMAIN, "set_cover_position", {"entity_id": entity_id, "position": 47}, blocking=True
        )
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args == call(
            False, 0x5, (zigpy.types.uint8_t,), 53, expect_reply=True, manufacturer=None
        )

    # stop from UI
    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=mock_coro([0x2, zcl_f.Status.SUCCESS]),
    ):
        await hass.services.async_call(
            DOMAIN, "stop_cover", {"entity_id": entity_id}, blocking=True
        )
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args == call(
            False, 0x2, (), expect_reply=True, manufacturer=None
        )
