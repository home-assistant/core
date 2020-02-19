"""Test zha light."""
from unittest.mock import call, sentinel

import asynctest
import pytest
import zigpy.profiles.zha
import zigpy.types
import zigpy.zcl.clusters.general as general
import zigpy.zcl.clusters.lighting as lighting
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.light import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE

from .common import (
    async_enable_traffic,
    async_test_rejoin,
    find_entity_id,
    make_attribute,
    make_zcl_header,
)

ON = 1
OFF = 0

LIGHT_ON_OFF = {
    1: {
        "device_type": zigpy.profiles.zha.DeviceType.ON_OFF_LIGHT,
        "in_clusters": [general.Basic.cluster_id, general.OnOff.cluster_id],
        "out_clusters": [general.Ota.cluster_id],
    }
}

LIGHT_LEVEL = {
    1: {
        "device_type": zigpy.profiles.zha.DeviceType.DIMMABLE_LIGHT,
        "in_clusters": [
            general.Basic.cluster_id,
            general.LevelControl.cluster_id,
            general.OnOff.cluster_id,
        ],
        "out_clusters": [general.Ota.cluster_id],
    }
}

LIGHT_COLOR = {
    1: {
        "device_type": zigpy.profiles.zha.DeviceType.COLOR_DIMMABLE_LIGHT,
        "in_clusters": [
            general.Basic.cluster_id,
            general.LevelControl.cluster_id,
            general.OnOff.cluster_id,
            lighting.Color.cluster_id,
        ],
        "out_clusters": [general.Ota.cluster_id],
    }
}


@asynctest.patch(
    "zigpy.zcl.clusters.lighting.Color.request",
    new=asynctest.CoroutineMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
@asynctest.patch(
    "zigpy.zcl.clusters.general.LevelControl.request",
    new=asynctest.CoroutineMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
@asynctest.patch(
    "zigpy.zcl.clusters.general.OnOff.request",
    new=asynctest.CoroutineMock(return_value=[sentinel.data, zcl_f.Status.SUCCESS]),
)
@pytest.mark.parametrize(
    "device, reporting",
    [(LIGHT_ON_OFF, (1, 0, 0)), (LIGHT_LEVEL, (1, 1, 0)), (LIGHT_COLOR, (1, 1, 3))],
)
async def test_light(
    hass, zigpy_device_mock, zha_device_joined_restored, device, reporting,
):
    """Test zha light platform."""

    # create zigpy devices
    zigpy_device = zigpy_device_mock(device)
    zha_device = await zha_device_joined_restored(zigpy_device)
    entity_id = await find_entity_id(DOMAIN, zha_device, hass)

    assert entity_id is not None

    cluster_on_off = zigpy_device.endpoints[1].on_off
    cluster_level = getattr(zigpy_device.endpoints[1], "level", None)
    cluster_color = getattr(zigpy_device.endpoints[1], "light_color", None)

    # test that the lights were created and that they are unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])

    # test that the lights were created and are off
    assert hass.states.get(entity_id).state == STATE_OFF

    # test turning the lights on and off from the light
    await async_test_on_off_from_light(hass, cluster_on_off, entity_id)

    # test turning the lights on and off from the HA
    await async_test_on_off_from_hass(hass, cluster_on_off, entity_id)

    if cluster_level:
        await async_test_level_on_off_from_hass(
            hass, cluster_on_off, cluster_level, entity_id
        )

        # test getting a brightness change from the network
        await async_test_on_from_light(hass, cluster_on_off, entity_id)
        await async_test_dimmer_from_light(
            hass, cluster_level, entity_id, 150, STATE_ON
        )

    # test rejoin
    await async_test_off_from_hass(hass, cluster_on_off, entity_id)
    clusters = [cluster_on_off]
    if cluster_level:
        clusters.append(cluster_level)
    if cluster_color:
        clusters.append(cluster_color)
    await async_test_rejoin(hass, zigpy_device, clusters, reporting)


async def async_test_on_off_from_light(hass, cluster, entity_id):
    """Test on off functionality from the light."""
    # turn on at light
    attr = make_attribute(0, 1)
    hdr = make_zcl_header(zcl_f.Command.Report_Attributes)
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    # turn off at light
    attr.value.value = 0
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF


async def async_test_on_from_light(hass, cluster, entity_id):
    """Test on off functionality from the light."""
    # turn on at light
    attr = make_attribute(0, 1)
    hdr = make_zcl_header(zcl_f.Command.Report_Attributes)
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON


async def async_test_on_off_from_hass(hass, cluster, entity_id):
    """Test on off functionality from hass."""
    # turn on via UI
    cluster.request.reset_mock()
    await hass.services.async_call(
        DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert cluster.request.call_count == 1
    assert cluster.request.await_count == 1
    assert cluster.request.call_args == call(
        False, ON, (), expect_reply=True, manufacturer=None
    )

    await async_test_off_from_hass(hass, cluster, entity_id)


async def async_test_off_from_hass(hass, cluster, entity_id):
    """Test turning off the light from Home Assistant."""

    # turn off via UI
    cluster.request.reset_mock()
    await hass.services.async_call(
        DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert cluster.request.call_count == 1
    assert cluster.request.await_count == 1
    assert cluster.request.call_args == call(
        False, OFF, (), expect_reply=True, manufacturer=None
    )


async def async_test_level_on_off_from_hass(
    hass, on_off_cluster, level_cluster, entity_id
):
    """Test on off functionality from hass."""

    on_off_cluster.request.reset_mock()
    # turn on via UI
    await hass.services.async_call(
        DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert on_off_cluster.request.call_count == 1
    assert on_off_cluster.request.await_count == 1
    assert level_cluster.request.call_count == 0
    assert level_cluster.request.await_count == 0
    assert on_off_cluster.request.call_args == call(
        False, 1, (), expect_reply=True, manufacturer=None
    )
    on_off_cluster.request.reset_mock()
    level_cluster.request.reset_mock()

    await hass.services.async_call(
        DOMAIN, "turn_on", {"entity_id": entity_id, "transition": 10}, blocking=True
    )
    assert on_off_cluster.request.call_count == 1
    assert on_off_cluster.request.await_count == 1
    assert level_cluster.request.call_count == 1
    assert level_cluster.request.await_count == 1
    assert on_off_cluster.request.call_args == call(
        False, 1, (), expect_reply=True, manufacturer=None
    )
    assert level_cluster.request.call_args == call(
        False,
        4,
        (zigpy.types.uint8_t, zigpy.types.uint16_t),
        254,
        100.0,
        expect_reply=True,
        manufacturer=None,
    )
    on_off_cluster.request.reset_mock()
    level_cluster.request.reset_mock()

    await hass.services.async_call(
        DOMAIN, "turn_on", {"entity_id": entity_id, "brightness": 10}, blocking=True
    )
    assert on_off_cluster.request.call_count == 1
    assert on_off_cluster.request.await_count == 1
    assert level_cluster.request.call_count == 1
    assert level_cluster.request.await_count == 1
    assert on_off_cluster.request.call_args == call(
        False, 1, (), expect_reply=True, manufacturer=None
    )
    assert level_cluster.request.call_args == call(
        False,
        4,
        (zigpy.types.uint8_t, zigpy.types.uint16_t),
        10,
        0,
        expect_reply=True,
        manufacturer=None,
    )
    on_off_cluster.request.reset_mock()
    level_cluster.request.reset_mock()

    await async_test_off_from_hass(hass, on_off_cluster, entity_id)


async def async_test_dimmer_from_light(hass, cluster, entity_id, level, expected_state):
    """Test dimmer functionality from the light."""
    attr = make_attribute(0, level)
    hdr = make_zcl_header(zcl_f.Command.Report_Attributes)
    cluster.handle_message(hdr, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == expected_state
    # hass uses None for brightness of 0 in state attributes
    if level == 0:
        level = None
    assert hass.states.get(entity_id).attributes.get("brightness") == level
