"""Test ZHA binary sensor."""

from unittest.mock import patch

import pytest
from zigpy.profiles import zha
from zigpy.zcl.clusters import general

from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import find_entity_id, send_attributes_report
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

ON = 1
OFF = 0


@pytest.fixture(autouse=True)
def binary_sensor_platform_only():
    """Only set up the binary_sensor and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.BINARY_SENSOR,
            Platform.SENSOR,
        ),
    ):
        yield


async def test_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_zha,
    zigpy_device_mock,
) -> None:
    """Test ZHA binary_sensor platform."""
    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_PROFILE: zha.PROFILE_ID,
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SENSOR,
                SIG_EP_INPUT: [general.Basic.cluster_id],
                SIG_EP_OUTPUT: [general.OnOff.cluster_id],
            }
        },
        ieee="01:2d:6f:00:0a:90:69:e8",
    )
    cluster = zigpy_device.endpoints[1].out_clusters[general.OnOff.cluster_id]

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)
    entity_id = find_entity_id(Platform.BINARY_SENSOR, zha_device_proxy, hass)
    assert entity_id is not None

    assert hass.states.get(entity_id).state == STATE_OFF

    await send_attributes_report(
        hass, cluster, {general.OnOff.AttributeDefs.on_off.id: ON}
    )
    assert hass.states.get(entity_id).state == STATE_ON

    await send_attributes_report(
        hass, cluster, {general.OnOff.AttributeDefs.on_off.id: OFF}
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    # test enable / disable sync w/ ZHA library
    entity_entry = entity_registry.async_get(entity_id)
    entity_key = (Platform.BINARY_SENSOR, entity_entry.unique_id)
    assert zha_device_proxy.device.platform_entities.get(entity_key).enabled

    entity_registry.async_update_entity(
        entity_id=entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert not zha_device_proxy.device.platform_entities.get(entity_key).enabled

    entity_registry.async_update_entity(entity_id=entity_id, disabled_by=None)
    await hass.async_block_till_done()

    assert zha_device_proxy.device.platform_entities.get(entity_key).enabled
