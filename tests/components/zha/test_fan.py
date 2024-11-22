"""Test ZHA fan."""

from unittest.mock import call, patch

import pytest
from zha.application.platforms.fan.const import PRESET_MODE_ON
from zigpy.profiles import zha
from zigpy.zcl.clusters import general, hvac

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    NotValidPresetModeError,
)
from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant

from .common import find_entity_id, send_attributes_report
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

ON = 1
OFF = 0


@pytest.fixture(autouse=True)
def fan_platform_only():
    """Only set up the fan and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.BUTTON,
            Platform.BINARY_SENSOR,
            Platform.FAN,
            Platform.LIGHT,
            Platform.DEVICE_TRACKER,
            Platform.NUMBER,
            Platform.SENSOR,
            Platform.SELECT,
            Platform.SWITCH,
        ),
    ):
        yield


async def test_fan(hass: HomeAssistant, setup_zha, zigpy_device_mock) -> None:
    """Test ZHA fan platform."""

    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.Basic.cluster_id, hvac.Fan.cluster_id],
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
    entity_id = find_entity_id(Platform.FAN, zha_device_proxy, hass)
    cluster = zigpy_device.endpoints[1].fan
    assert entity_id is not None

    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on at fan
    await send_attributes_report(
        hass,
        cluster,
        {hvac.Fan.AttributeDefs.fan_mode.id: hvac.FanMode.Low},
    )
    assert hass.states.get(entity_id).state == STATE_ON

    # turn off at fan
    await send_attributes_report(
        hass, cluster, {hvac.Fan.AttributeDefs.fan_mode.id: hvac.FanMode.Off}
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on from HA
    cluster.write_attributes.reset_mock()
    await async_turn_on(hass, entity_id)
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 2}, manufacturer=None)
    ]

    # turn off from HA
    cluster.write_attributes.reset_mock()
    await async_turn_off(hass, entity_id)
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 0}, manufacturer=None)
    ]

    # change speed from HA
    cluster.write_attributes.reset_mock()
    await async_set_percentage(hass, entity_id, percentage=100)
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 3}, manufacturer=None)
    ]

    # change preset_mode from HA
    cluster.write_attributes.reset_mock()
    await async_set_preset_mode(hass, entity_id, preset_mode=PRESET_MODE_ON)
    assert cluster.write_attributes.mock_calls == [
        call({"fan_mode": 4}, manufacturer=None)
    ]

    # set invalid preset_mode from HA
    cluster.write_attributes.reset_mock()
    with pytest.raises(NotValidPresetModeError) as exc:
        await async_set_preset_mode(
            hass, entity_id, preset_mode="invalid does not exist"
        )
    assert exc.value.translation_key == "not_valid_preset_mode"
    assert len(cluster.write_attributes.mock_calls) == 0


async def async_turn_on(hass: HomeAssistant, entity_id, percentage=None):
    """Turn fan on."""
    data = {
        key: value
        for key, value in ((ATTR_ENTITY_ID, entity_id), (ATTR_PERCENTAGE, percentage))
        if value is not None
    }

    await hass.services.async_call(Platform.FAN, SERVICE_TURN_ON, data, blocking=True)


async def async_turn_off(hass: HomeAssistant, entity_id):
    """Turn fan off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    await hass.services.async_call(Platform.FAN, SERVICE_TURN_OFF, data, blocking=True)


async def async_set_percentage(hass: HomeAssistant, entity_id, percentage=None):
    """Set percentage for specified fan."""
    data = {
        key: value
        for key, value in ((ATTR_ENTITY_ID, entity_id), (ATTR_PERCENTAGE, percentage))
        if value is not None
    }

    await hass.services.async_call(
        Platform.FAN, SERVICE_SET_PERCENTAGE, data, blocking=True
    )


async def async_set_preset_mode(hass: HomeAssistant, entity_id, preset_mode=None):
    """Set preset_mode for specified fan."""
    data = {
        key: value
        for key, value in ((ATTR_ENTITY_ID, entity_id), (ATTR_PRESET_MODE, preset_mode))
        if value is not None
    }

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_SET_PRESET_MODE, data, blocking=True
    )
