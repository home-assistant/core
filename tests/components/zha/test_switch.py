"""Test ZHA switch."""

from unittest.mock import call, patch

import pytest
from zigpy.profiles import zha
from zigpy.zcl.clusters import general
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import find_entity_id, send_attributes_report
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

ON = 1
OFF = 0


@pytest.fixture(autouse=True)
def switch_platform_only():
    """Only set up the switch and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.DEVICE_TRACKER,
            Platform.SENSOR,
            Platform.SELECT,
            Platform.SWITCH,
        ),
    ):
        yield


async def test_switch(hass: HomeAssistant, setup_zha, zigpy_device_mock) -> None:
    """Test ZHA switch platform."""

    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    general.OnOff.cluster_id,
                    general.Groups.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        ieee="01:2d:6f:00:0a:90:69:e8",
        node_descriptor=b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00",
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)
    entity_id = find_entity_id(Platform.SWITCH, zha_device_proxy, hass)
    cluster = zigpy_device.endpoints[1].on_off
    assert entity_id is not None

    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on at switch
    await send_attributes_report(
        hass, cluster, {general.OnOff.AttributeDefs.on_off.id: ON}
    )
    assert hass.states.get(entity_id).state == STATE_ON

    # turn off at switch
    await send_attributes_report(
        hass, cluster, {general.OnOff.AttributeDefs.on_off.id: OFF}
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on from HA
    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=[0x00, zcl_f.Status.SUCCESS],
    ):
        # turn on via UI
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
        )
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args == call(
            False,
            ON,
            cluster.commands_by_name["on"].schema,
            expect_reply=True,
            manufacturer=None,
            tsn=None,
        )
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_ON

    # turn off from HA
    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=[0x01, zcl_f.Status.SUCCESS],
    ):
        # turn off via UI
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
        )
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args == call(
            False,
            OFF,
            cluster.commands_by_name["off"].schema,
            expect_reply=True,
            manufacturer=None,
            tsn=None,
        )
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_OFF

    await async_setup_component(hass, "homeassistant", {})

    cluster.read_attributes.reset_mock()
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert len(cluster.read_attributes.mock_calls) == 1
    assert cluster.read_attributes.call_args == call(
        ["on_off"], allow_cache=False, only_cache=False, manufacturer=None
    )
