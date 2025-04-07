"""Test ZHA button."""

from unittest.mock import patch

from freezegun import freeze_time
import pytest
from zigpy.const import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE
from zigpy.profiles import zha
from zigpy.zcl.clusters import general
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    SERVICE_PRESS,
    ButtonDeviceClass,
)
from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import find_entity_id


@pytest.fixture(autouse=True)
def button_platform_only():
    """Only set up the button and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR),
    ):
        yield


@pytest.fixture
async def setup_zha_integration(hass: HomeAssistant, setup_zha):
    """Set up ZHA component."""

    # if we call this in the test itself the test hangs forever
    await setup_zha()


@freeze_time("2021-11-04 17:37:00", tz_offset=-1)
async def test_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_zha_integration,  # pylint: disable=unused-argument
    zigpy_device_mock,
) -> None:
    """Test ZHA button platform."""

    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_PROFILE: zha.PROFILE_ID,
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SENSOR,
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    general.Identify.cluster_id,
                ],
                SIG_EP_OUTPUT: [general.OnOff.cluster_id],
            }
        },
        ieee="01:2d:6f:00:0a:90:69:e8",
    )
    cluster = zigpy_device.endpoints[1].identify

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)
    entity_id = find_entity_id(Platform.BUTTON, zha_device_proxy, hass)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_DEVICE_CLASS] == ButtonDeviceClass.IDENTIFY

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.entity_category == EntityCategory.DIAGNOSTIC

    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=[0x00, zcl_f.Status.SUCCESS],
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args[0][0] is False
        assert cluster.request.call_args[0][1] == 0
        assert cluster.request.call_args[0][3] == 5  # duration in seconds

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "2021-11-04T16:37:00+00:00"
    assert state.attributes[ATTR_DEVICE_CLASS] == ButtonDeviceClass.IDENTIFY
