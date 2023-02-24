"""Test ZHA cover."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import zigpy.profiles.zha
import zigpy.types
import zigpy.zcl.clusters.closures as closures
import zigpy.zcl.clusters.general as general
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
)
from homeassistant.components.zha.core.const import ZHA_EVENT
from homeassistant.const import (
    ATTR_COMMAND,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import CoreState, HomeAssistant, State

from .common import (
    async_enable_traffic,
    async_test_rejoin,
    find_entity_id,
    make_zcl_header,
    send_attributes_report,
)
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

from tests.common import async_capture_events, mock_coro, mock_restore_cache


@pytest.fixture(autouse=True)
def cover_platform_only():
    """Only set up the cover and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.COVER,
            Platform.DEVICE_TRACKER,
            Platform.NUMBER,
            Platform.SELECT,
        ),
    ):
        yield


@pytest.fixture
def zigpy_cover_device(zigpy_device_mock):
    """Zigpy cover device."""

    endpoints = {
        1: {
            SIG_EP_PROFILE: zigpy.profiles.zha.PROFILE_ID,
            SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.IAS_ZONE,
            SIG_EP_INPUT: [closures.WindowCovering.cluster_id],
            SIG_EP_OUTPUT: [],
        }
    }
    return zigpy_device_mock(endpoints)


@pytest.fixture
def zigpy_cover_remote(zigpy_device_mock):
    """Zigpy cover remote device."""

    endpoints = {
        1: {
            SIG_EP_PROFILE: zigpy.profiles.zha.PROFILE_ID,
            SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.WINDOW_COVERING_CONTROLLER,
            SIG_EP_INPUT: [],
            SIG_EP_OUTPUT: [closures.WindowCovering.cluster_id],
        }
    }
    return zigpy_device_mock(endpoints)


@pytest.fixture
def zigpy_shade_device(zigpy_device_mock):
    """Zigpy shade device."""

    endpoints = {
        1: {
            SIG_EP_PROFILE: zigpy.profiles.zha.PROFILE_ID,
            SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.SHADE,
            SIG_EP_INPUT: [
                closures.Shade.cluster_id,
                general.LevelControl.cluster_id,
                general.OnOff.cluster_id,
            ],
            SIG_EP_OUTPUT: [],
        }
    }
    return zigpy_device_mock(endpoints)


@pytest.fixture
def zigpy_keen_vent(zigpy_device_mock):
    """Zigpy Keen Vent device."""

    endpoints = {
        1: {
            SIG_EP_PROFILE: zigpy.profiles.zha.PROFILE_ID,
            SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.LEVEL_CONTROLLABLE_OUTPUT,
            SIG_EP_INPUT: [general.LevelControl.cluster_id, general.OnOff.cluster_id],
            SIG_EP_OUTPUT: [],
        }
    }
    return zigpy_device_mock(
        endpoints, manufacturer="Keen Home Inc", model="SV02-612-MP-1.3"
    )


async def test_cover(
    hass: HomeAssistant, zha_device_joined_restored, zigpy_cover_device
) -> None:
    """Test ZHA cover platform."""

    # load up cover domain
    cluster = zigpy_cover_device.endpoints.get(1).window_covering
    cluster.PLUGGED_ATTR_READS = {"current_position_lift_percentage": 100}
    zha_device = await zha_device_joined_restored(zigpy_cover_device)
    assert cluster.read_attributes.call_count == 1
    assert "current_position_lift_percentage" in cluster.read_attributes.call_args[0][0]

    entity_id = await find_entity_id(Platform.COVER, zha_device, hass)
    assert entity_id is not None

    await async_enable_traffic(hass, [zha_device], enabled=False)
    # test that the cover was created and that it is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])
    await hass.async_block_till_done()

    # test that the state has changed from unavailable to off
    await send_attributes_report(hass, cluster, {0: 0, 8: 100, 1: 1})
    assert hass.states.get(entity_id).state == STATE_CLOSED

    # test to see if it opens
    await send_attributes_report(hass, cluster, {0: 1, 8: 0, 1: 100})
    assert hass.states.get(entity_id).state == STATE_OPEN

    # close from UI
    with patch(
        "zigpy.zcl.Cluster.request", return_value=mock_coro([0x1, zcl_f.Status.SUCCESS])
    ):
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_CLOSE_COVER, {"entity_id": entity_id}, blocking=True
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args[0][0] is False
        assert cluster.request.call_args[0][1] == 0x01
        assert cluster.request.call_args[0][2].command.name == "down_close"
        assert cluster.request.call_args[1]["expect_reply"] is True

    # open from UI
    with patch(
        "zigpy.zcl.Cluster.request", return_value=mock_coro([0x0, zcl_f.Status.SUCCESS])
    ):
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_OPEN_COVER, {"entity_id": entity_id}, blocking=True
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args[0][0] is False
        assert cluster.request.call_args[0][1] == 0x00
        assert cluster.request.call_args[0][2].command.name == "up_open"
        assert cluster.request.call_args[1]["expect_reply"] is True

    # set position UI
    with patch(
        "zigpy.zcl.Cluster.request", return_value=mock_coro([0x5, zcl_f.Status.SUCCESS])
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {"entity_id": entity_id, "position": 47},
            blocking=True,
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args[0][0] is False
        assert cluster.request.call_args[0][1] == 0x05
        assert cluster.request.call_args[0][2].command.name == "go_to_lift_percentage"
        assert cluster.request.call_args[0][3] == 53
        assert cluster.request.call_args[1]["expect_reply"] is True

    # stop from UI
    with patch(
        "zigpy.zcl.Cluster.request", return_value=mock_coro([0x2, zcl_f.Status.SUCCESS])
    ):
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_STOP_COVER, {"entity_id": entity_id}, blocking=True
        )
        assert cluster.request.call_count == 1
        assert cluster.request.call_args[0][0] is False
        assert cluster.request.call_args[0][1] == 0x02
        assert cluster.request.call_args[0][2].command.name == "stop"
        assert cluster.request.call_args[1]["expect_reply"] is True

    # test rejoin
    cluster.PLUGGED_ATTR_READS = {"current_position_lift_percentage": 0}
    await async_test_rejoin(hass, zigpy_cover_device, [cluster], (1,))
    assert hass.states.get(entity_id).state == STATE_OPEN


async def test_shade(
    hass: HomeAssistant, zha_device_joined_restored, zigpy_shade_device
) -> None:
    """Test ZHA cover platform for shade device type."""

    # load up cover domain
    zha_device = await zha_device_joined_restored(zigpy_shade_device)

    cluster_on_off = zigpy_shade_device.endpoints.get(1).on_off
    cluster_level = zigpy_shade_device.endpoints.get(1).level
    entity_id = await find_entity_id(Platform.COVER, zha_device, hass)
    assert entity_id is not None

    await async_enable_traffic(hass, [zha_device], enabled=False)
    # test that the cover was created and that it is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])
    await hass.async_block_till_done()

    # test that the state has changed from unavailable to off
    await send_attributes_report(hass, cluster_on_off, {8: 0, 0: False, 1: 1})
    assert hass.states.get(entity_id).state == STATE_CLOSED

    # test to see if it opens
    await send_attributes_report(hass, cluster_on_off, {8: 0, 0: True, 1: 1})
    assert hass.states.get(entity_id).state == STATE_OPEN

    # close from UI command fails
    with patch("zigpy.zcl.Cluster.request", side_effect=asyncio.TimeoutError):
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_CLOSE_COVER, {"entity_id": entity_id}, blocking=True
        )
        assert cluster_on_off.request.call_count == 1
        assert cluster_on_off.request.call_args[0][0] is False
        assert cluster_on_off.request.call_args[0][1] == 0x0000
        assert hass.states.get(entity_id).state == STATE_OPEN

    with patch(
        "zigpy.zcl.Cluster.request", AsyncMock(return_value=[0x1, zcl_f.Status.SUCCESS])
    ):
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_CLOSE_COVER, {"entity_id": entity_id}, blocking=True
        )
        assert cluster_on_off.request.call_count == 1
        assert cluster_on_off.request.call_args[0][0] is False
        assert cluster_on_off.request.call_args[0][1] == 0x0000
        assert hass.states.get(entity_id).state == STATE_CLOSED

    # open from UI command fails
    assert ATTR_CURRENT_POSITION not in hass.states.get(entity_id).attributes
    await send_attributes_report(hass, cluster_level, {0: 0})
    with patch("zigpy.zcl.Cluster.request", side_effect=asyncio.TimeoutError):
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_OPEN_COVER, {"entity_id": entity_id}, blocking=True
        )
        assert cluster_on_off.request.call_count == 1
        assert cluster_on_off.request.call_args[0][0] is False
        assert cluster_on_off.request.call_args[0][1] == 0x0001
        assert hass.states.get(entity_id).state == STATE_CLOSED

    # open from UI succeeds
    with patch(
        "zigpy.zcl.Cluster.request", AsyncMock(return_value=[0x0, zcl_f.Status.SUCCESS])
    ):
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_OPEN_COVER, {"entity_id": entity_id}, blocking=True
        )
        assert cluster_on_off.request.call_count == 1
        assert cluster_on_off.request.call_args[0][0] is False
        assert cluster_on_off.request.call_args[0][1] == 0x0001
        assert hass.states.get(entity_id).state == STATE_OPEN

    # set position UI command fails
    with patch("zigpy.zcl.Cluster.request", side_effect=asyncio.TimeoutError):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {"entity_id": entity_id, "position": 47},
            blocking=True,
        )
        assert cluster_level.request.call_count == 1
        assert cluster_level.request.call_args[0][0] is False
        assert cluster_level.request.call_args[0][1] == 0x0004
        assert int(cluster_level.request.call_args[0][3] * 100 / 255) == 47
        assert hass.states.get(entity_id).attributes[ATTR_CURRENT_POSITION] == 0

    # set position UI success
    with patch(
        "zigpy.zcl.Cluster.request", AsyncMock(return_value=[0x5, zcl_f.Status.SUCCESS])
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {"entity_id": entity_id, "position": 47},
            blocking=True,
        )
        assert cluster_level.request.call_count == 1
        assert cluster_level.request.call_args[0][0] is False
        assert cluster_level.request.call_args[0][1] == 0x0004
        assert int(cluster_level.request.call_args[0][3] * 100 / 255) == 47
        assert hass.states.get(entity_id).attributes[ATTR_CURRENT_POSITION] == 47

    # report position change
    await send_attributes_report(hass, cluster_level, {8: 0, 0: 100, 1: 1})
    assert hass.states.get(entity_id).attributes[ATTR_CURRENT_POSITION] == int(
        100 * 100 / 255
    )

    # test rejoin
    await async_test_rejoin(
        hass, zigpy_shade_device, [cluster_level, cluster_on_off], (1,)
    )
    assert hass.states.get(entity_id).state == STATE_OPEN

    # test cover stop
    with patch("zigpy.zcl.Cluster.request", side_effect=asyncio.TimeoutError):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {"entity_id": entity_id},
            blocking=True,
        )
        assert cluster_level.request.call_count == 1
        assert cluster_level.request.call_args[0][0] is False
        assert cluster_level.request.call_args[0][1] in (0x0003, 0x0007)


async def test_restore_state(
    hass: HomeAssistant, zha_device_restored, zigpy_shade_device
) -> None:
    """Ensure states are restored on startup."""

    mock_restore_cache(
        hass,
        (
            State(
                "cover.fakemanufacturer_fakemodel_shade",
                STATE_OPEN,
                {ATTR_CURRENT_POSITION: 50},
            ),
        ),
    )

    hass.state = CoreState.starting

    zha_device = await zha_device_restored(zigpy_shade_device)
    entity_id = await find_entity_id(Platform.COVER, zha_device, hass)
    assert entity_id is not None

    # test that the cover was created and that it is unavailable
    assert hass.states.get(entity_id).state == STATE_OPEN
    assert hass.states.get(entity_id).attributes[ATTR_CURRENT_POSITION] == 50


async def test_keen_vent(
    hass: HomeAssistant, zha_device_joined_restored, zigpy_keen_vent
) -> None:
    """Test keen vent."""

    # load up cover domain
    zha_device = await zha_device_joined_restored(zigpy_keen_vent)

    cluster_on_off = zigpy_keen_vent.endpoints.get(1).on_off
    cluster_level = zigpy_keen_vent.endpoints.get(1).level
    entity_id = await find_entity_id(Platform.COVER, zha_device, hass)
    assert entity_id is not None

    await async_enable_traffic(hass, [zha_device], enabled=False)
    # test that the cover was created and that it is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])
    await hass.async_block_till_done()

    # test that the state has changed from unavailable to off
    await send_attributes_report(hass, cluster_on_off, {8: 0, 0: False, 1: 1})
    assert hass.states.get(entity_id).state == STATE_CLOSED

    # open from UI command fails
    p1 = patch.object(cluster_on_off, "request", side_effect=asyncio.TimeoutError)
    p2 = patch.object(cluster_level, "request", AsyncMock(return_value=[4, 0]))

    with p1, p2:
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_OPEN_COVER, {"entity_id": entity_id}, blocking=True
        )
        assert cluster_on_off.request.call_count == 1
        assert cluster_on_off.request.call_args[0][0] is False
        assert cluster_on_off.request.call_args[0][1] == 0x0001
        assert cluster_level.request.call_count == 1
        assert hass.states.get(entity_id).state == STATE_CLOSED

    # open from UI command success
    p1 = patch.object(cluster_on_off, "request", AsyncMock(return_value=[1, 0]))
    p2 = patch.object(cluster_level, "request", AsyncMock(return_value=[4, 0]))

    with p1, p2:
        await hass.services.async_call(
            COVER_DOMAIN, SERVICE_OPEN_COVER, {"entity_id": entity_id}, blocking=True
        )
        await asyncio.sleep(0)
        assert cluster_on_off.request.call_count == 1
        assert cluster_on_off.request.call_args[0][0] is False
        assert cluster_on_off.request.call_args[0][1] == 0x0001
        assert cluster_level.request.call_count == 1
        assert hass.states.get(entity_id).state == STATE_OPEN
        assert hass.states.get(entity_id).attributes[ATTR_CURRENT_POSITION] == 100


async def test_cover_remote(
    hass: HomeAssistant, zha_device_joined_restored, zigpy_cover_remote
) -> None:
    """Test ZHA cover remote."""

    # load up cover domain
    await zha_device_joined_restored(zigpy_cover_remote)

    cluster = zigpy_cover_remote.endpoints[1].out_clusters[
        closures.WindowCovering.cluster_id
    ]
    zha_events = async_capture_events(hass, ZHA_EVENT)

    # up command
    hdr = make_zcl_header(0, global_command=False)
    cluster.handle_message(hdr, [])
    await hass.async_block_till_done()

    assert len(zha_events) == 1
    assert zha_events[0].data[ATTR_COMMAND] == "up_open"

    # down command
    hdr = make_zcl_header(1, global_command=False)
    cluster.handle_message(hdr, [])
    await hass.async_block_till_done()

    assert len(zha_events) == 2
    assert zha_events[1].data[ATTR_COMMAND] == "down_close"
