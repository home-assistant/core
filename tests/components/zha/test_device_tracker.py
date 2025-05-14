"""Test ZHA Device Tracker."""

from datetime import timedelta
import time
from unittest.mock import patch

import pytest
from zha.application.registries import SMARTTHINGS_ARRIVAL_SENSOR_DEVICE_TYPE
from zigpy.profiles import zha
from zigpy.zcl.clusters import general

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .common import find_entity_id, send_attributes_report
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

from tests.common import async_fire_time_changed


@pytest.fixture(autouse=True)
def device_tracker_platforms_only():
    """Only set up the device_tracker platforms and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.DEVICE_TRACKER,
            Platform.BUTTON,
            Platform.SELECT,
            Platform.NUMBER,
            Platform.BINARY_SENSOR,
            Platform.SENSOR,
        ),
    ):
        yield


async def test_device_tracker(
    hass: HomeAssistant, setup_zha, zigpy_device_mock
) -> None:
    """Test ZHA device tracker platform."""

    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    general.PowerConfiguration.cluster_id,
                    general.Identify.cluster_id,
                    general.PollControl.cluster_id,
                    general.BinaryInput.cluster_id,
                ],
                SIG_EP_OUTPUT: [general.Identify.cluster_id, general.Ota.cluster_id],
                SIG_EP_TYPE: SMARTTHINGS_ARRIVAL_SENSOR_DEVICE_TYPE,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        }
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)
    entity_id = find_entity_id(Platform.DEVICE_TRACKER, zha_device_proxy, hass)
    cluster = zigpy_device.endpoints[1].power
    assert entity_id is not None

    # test that the state has changed from unavailable to not home
    assert hass.states.get(entity_id).state == STATE_NOT_HOME

    # turn state flip
    await send_attributes_report(
        hass, cluster, {0x0000: 0, 0x0020: 23, 0x0021: 200, 0x0001: 2}
    )

    zigpy_device.last_seen = time.time() + 10
    next_update = dt_util.utcnow() + timedelta(seconds=30)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_HOME

    entity = hass.data[Platform.DEVICE_TRACKER].get_entity(entity_id)

    assert entity.is_connected is True
    assert entity.source_type == SourceType.ROUTER
    assert entity.battery_level == 100
