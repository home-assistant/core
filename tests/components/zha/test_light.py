"""Test zha light."""
import asyncio
from unittest.mock import MagicMock, call, patch, sentinel

from homeassistant.components.light import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE

from .common import (
    async_enable_traffic, async_init_zigpy_device, async_test_device_join,
    make_attribute, make_entity_id)

from tests.common import mock_coro

ON = 1
OFF = 0


async def test_light(hass, config_entry, zha_gateway, monkeypatch):
    """Test zha light platform."""
    from zigpy.zcl.clusters.general import OnOff, LevelControl, Basic
    from zigpy.zcl.foundation import Status
    from zigpy.profiles.zha import DeviceType

    # create zigpy devices
    zigpy_device_on_off = await async_init_zigpy_device(
        hass,
        [OnOff.cluster_id, Basic.cluster_id],
        [],
        DeviceType.ON_OFF_LIGHT,
        zha_gateway
    )

    zigpy_device_level = await async_init_zigpy_device(
        hass,
        [OnOff.cluster_id, LevelControl.cluster_id, Basic.cluster_id],
        [],
        DeviceType.ON_OFF_LIGHT,
        zha_gateway,
        ieee="00:0d:6f:11:0a:90:69:e7",
        manufacturer="FakeLevelManufacturer",
        model="FakeLevelModel"
    )

    # load up light domain
    await hass.config_entries.async_forward_entry_setup(
        config_entry, DOMAIN)
    await hass.async_block_till_done()

    # on off light
    on_off_device_on_off_cluster = zigpy_device_on_off.endpoints.get(1).on_off
    on_off_entity_id = make_entity_id(DOMAIN, zigpy_device_on_off,
                                      on_off_device_on_off_cluster,
                                      use_suffix=False)
    on_off_zha_device = zha_gateway.get_device(zigpy_device_on_off.ieee)

    # dimmable light
    level_device_on_off_cluster = zigpy_device_level.endpoints.get(1).on_off
    level_device_level_cluster = zigpy_device_level.endpoints.get(1).level
    on_off_mock = MagicMock(side_effect=asyncio.coroutine(MagicMock(
        return_value=(sentinel.data, Status.SUCCESS))))
    level_mock = MagicMock(side_effect=asyncio.coroutine(MagicMock(
        return_value=(sentinel.data, Status.SUCCESS))))
    monkeypatch.setattr(level_device_on_off_cluster, 'request', on_off_mock)
    monkeypatch.setattr(level_device_level_cluster, 'request', level_mock)
    level_entity_id = make_entity_id(DOMAIN, zigpy_device_level,
                                     level_device_on_off_cluster,
                                     use_suffix=False)
    level_zha_device = zha_gateway.get_device(zigpy_device_level.ieee)

    # test that the lights were created and that they are unavailable
    assert hass.states.get(on_off_entity_id).state == STATE_UNAVAILABLE
    assert hass.states.get(level_entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, zha_gateway,
                               [on_off_zha_device, level_zha_device])

    # test that the lights were created and are off
    assert hass.states.get(on_off_entity_id).state == STATE_OFF
    assert hass.states.get(level_entity_id).state == STATE_OFF

    # test turning the lights on and off from the light
    await async_test_on_off_from_light(
        hass, on_off_device_on_off_cluster, on_off_entity_id)

    await async_test_on_off_from_light(
        hass, level_device_on_off_cluster, level_entity_id)

    # test turning the lights on and off from the HA
    await async_test_on_off_from_hass(
        hass, on_off_device_on_off_cluster, on_off_entity_id)

    await async_test_level_on_off_from_hass(
        hass, level_device_on_off_cluster, level_device_level_cluster,
        level_entity_id)

    # test turning the lights on and off from the light
    await async_test_on_from_light(
        hass, level_device_on_off_cluster, level_entity_id)

    # test getting a brightness change from the network
    await async_test_dimmer_from_light(
        hass, level_device_level_cluster, level_entity_id, 150, STATE_ON)

    # test adding a new light to the network and HA
    await async_test_device_join(
        hass, zha_gateway, OnOff.cluster_id,
        DOMAIN, device_type=DeviceType.ON_OFF_LIGHT)


async def async_test_on_off_from_light(hass, cluster, entity_id):
    """Test on off functionality from the light."""
    # turn on at light
    attr = make_attribute(0, 1)
    cluster.handle_message(False, 1, 0x0a, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    # turn off at light
    attr.value.value = 0
    cluster.handle_message(False, 0, 0x0a, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF


async def async_test_on_from_light(hass, cluster, entity_id):
    """Test on off functionality from the light."""
    # turn on at light
    attr = make_attribute(0, 1)
    cluster.handle_message(False, 1, 0x0a, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON


async def async_test_on_off_from_hass(hass, cluster, entity_id):
    """Test on off functionality from hass."""
    from zigpy.zcl.foundation import Status
    with patch(
            'zigpy.zcl.Cluster.request',
            return_value=mock_coro([Status.SUCCESS, Status.SUCCESS])):
        # turn on via UI
        await hass.services.async_call(DOMAIN, 'turn_on', {
            'entity_id': entity_id
        }, blocking=True)
        assert cluster.request.call_count == 1
        assert cluster.request.call_args == call(
            False, ON, (), expect_reply=True, manufacturer=None)

    await async_test_off_from_hass(hass, cluster, entity_id)


async def async_test_off_from_hass(hass, cluster, entity_id):
    """Test turning off the light from homeassistant."""
    from zigpy.zcl.foundation import Status
    with patch(
            'zigpy.zcl.Cluster.request',
            return_value=mock_coro([Status.SUCCESS, Status.SUCCESS])):
        # turn off via UI
        await hass.services.async_call(DOMAIN, 'turn_off', {
            'entity_id': entity_id
        }, blocking=True)
        assert cluster.request.call_count == 1
        assert cluster.request.call_args == call(
            False, OFF, (), expect_reply=True, manufacturer=None)


async def async_test_level_on_off_from_hass(hass, on_off_cluster,
                                            level_cluster, entity_id):
    """Test on off functionality from hass."""
    from zigpy import types
    # turn on via UI
    await hass.services.async_call(DOMAIN, 'turn_on', {'entity_id': entity_id},
                                   blocking=True)
    assert on_off_cluster.request.call_count == 1
    assert level_cluster.request.call_count == 0
    assert on_off_cluster.request.call_args == call(
        False, 1, (), expect_reply=True, manufacturer=None)
    on_off_cluster.request.reset_mock()
    level_cluster.request.reset_mock()

    await hass.services.async_call(DOMAIN, 'turn_on',
                                   {'entity_id': entity_id, 'transition': 10},
                                   blocking=True)
    assert on_off_cluster.request.call_count == 1
    assert level_cluster.request.call_count == 1
    assert on_off_cluster.request.call_args == call(
        False, 1, (), expect_reply=True, manufacturer=None)
    assert level_cluster.request.call_args == call(
        False, 4, (types.uint8_t, types.uint16_t), 254, 100.0,
        expect_reply=True, manufacturer=None)
    on_off_cluster.request.reset_mock()
    level_cluster.request.reset_mock()

    await hass.services.async_call(DOMAIN, 'turn_on',
                                   {'entity_id': entity_id, 'brightness': 10},
                                   blocking=True)
    assert on_off_cluster.request.call_count == 1
    assert level_cluster.request.call_count == 1
    assert on_off_cluster.request.call_args == call(
        False, 1, (), expect_reply=True, manufacturer=None)
    assert level_cluster.request.call_args == call(
        False, 4, (types.uint8_t, types.uint16_t), 10, 5.0,
        expect_reply=True, manufacturer=None)
    on_off_cluster.request.reset_mock()
    level_cluster.request.reset_mock()

    await async_test_off_from_hass(hass, on_off_cluster, entity_id)


async def async_test_dimmer_from_light(hass, cluster, entity_id,
                                       level, expected_state):
    """Test dimmer functionality from the light."""
    attr = make_attribute(0, level)
    cluster.handle_message(False, 1, 0x0a, [[attr]])
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == expected_state
    # hass uses None for brightness of 0 in state attributes
    if level == 0:
        level = None
    assert hass.states.get(entity_id).attributes.get('brightness') == level
