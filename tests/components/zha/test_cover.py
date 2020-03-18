"""Test zha cover."""
from unittest.mock import MagicMock, call, patch

import asynctest
import pytest
import zigpy.types
import zigpy.zcl.clusters.closures as closures
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.cover import DOMAIN
from homeassistant.const import STATE_CLOSED, STATE_OPEN, STATE_UNAVAILABLE

from .common import (
    async_enable_traffic,
    async_test_rejoin,
    find_entity_id,
    make_attribute,
    make_zcl_header,
)

from tests.common import mock_coro


@pytest.fixture
def zigpy_cover_device(zigpy_device_mock):
    """Zigpy cover device."""

    endpoints = {
        1: {
            "device_type": 1026,
            "in_clusters": [closures.WindowCovering.cluster_id],
            "out_clusters": [],
        }
    }
    return zigpy_device_mock(endpoints)


@asynctest.patch(
    "homeassistant.components.zha.core.channels.closures.WindowCovering.async_initialize"
)
async def test_cover(m1, hass, zha_device_joined_restored, zigpy_cover_device):
    """Test zha cover platform."""

    async def get_chan_attr(*args, **kwargs):
        return 100

    with patch(
        "homeassistant.components.zha.core.channels.ZigbeeChannel.get_attribute_value",
        new=MagicMock(side_effect=get_chan_attr),
    ) as get_attr_mock:
        # load up cover domain
        zha_device = await zha_device_joined_restored(zigpy_cover_device)
        assert get_attr_mock.call_count == 2
        assert get_attr_mock.call_args[0][0] == "current_position_lift_percentage"

    cluster = zigpy_cover_device.endpoints.get(1).window_covering
    entity_id = await find_entity_id(DOMAIN, zha_device, hass)
    assert entity_id is not None

    # test that the cover was created and that it is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])
    await hass.async_block_till_done()

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
        "zigpy.zcl.Cluster.request", return_value=mock_coro([0x1, zcl_f.Status.SUCCESS])
    ):
        await hass.services.async_call(
            DOMAIN, "close_cover", {"entity_id": entity_id}, blocking=True
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args == call(
            False, 0x1, (), expect_reply=True, manufacturer=None
        )

    # open from UI
    with patch(
        "zigpy.zcl.Cluster.request", return_value=mock_coro([0x0, zcl_f.Status.SUCCESS])
    ):
        await hass.services.async_call(
            DOMAIN, "open_cover", {"entity_id": entity_id}, blocking=True
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args == call(
            False, 0x0, (), expect_reply=True, manufacturer=None
        )

    # set position UI
    with patch(
        "zigpy.zcl.Cluster.request", return_value=mock_coro([0x5, zcl_f.Status.SUCCESS])
    ):
        await hass.services.async_call(
            DOMAIN,
            "set_cover_position",
            {"entity_id": entity_id, "position": 47},
            blocking=True,
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args == call(
            False, 0x5, (zigpy.types.uint8_t,), 53, expect_reply=True, manufacturer=None
        )

    # stop from UI
    with patch(
        "zigpy.zcl.Cluster.request", return_value=mock_coro([0x2, zcl_f.Status.SUCCESS])
    ):
        await hass.services.async_call(
            DOMAIN, "stop_cover", {"entity_id": entity_id}, blocking=True
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args == call(
            False, 0x2, (), expect_reply=True, manufacturer=None
        )

    # test rejoin
    await async_test_rejoin(hass, zigpy_cover_device, [cluster], (1,))
    assert hass.states.get(entity_id).state == STATE_OPEN
