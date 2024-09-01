"""Test ZHA analog output."""

from unittest.mock import call, patch

import pytest
from zigpy.profiles import zha
from zigpy.zcl.clusters import general
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import find_entity_id, send_attributes_report, update_attribute_cache
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE


@pytest.fixture(autouse=True)
def number_platform_only():
    """Only set up the number and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.BUTTON,
            Platform.DEVICE_TRACKER,
            Platform.LIGHT,
            Platform.NUMBER,
            Platform.SELECT,
            Platform.SENSOR,
        ),
    ):
        yield


async def test_number(hass: HomeAssistant, setup_zha, zigpy_device_mock) -> None:
    """Test ZHA number platform."""

    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_TYPE: zha.DeviceType.LEVEL_CONTROL_SWITCH,
                SIG_EP_INPUT: [
                    general.AnalogOutput.cluster_id,
                    general.Basic.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        }
    )

    cluster = zigpy_device.endpoints[1].analog_output
    cluster.PLUGGED_ATTR_READS = {
        "max_present_value": 100.0,
        "min_present_value": 1.0,
        "relinquish_default": 50.0,
        "resolution": 1.1,
        "description": "PWM1",
        "engineering_units": 98,
        "application_type": 4 * 0x10000,
    }
    update_attribute_cache(cluster)
    cluster.PLUGGED_ATTR_READS["present_value"] = 15.0

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)
    entity_id = find_entity_id(Platform.NUMBER, zha_device_proxy, hass)
    assert entity_id is not None

    assert hass.states.get(entity_id).state == "15.0"

    # test attributes
    assert hass.states.get(entity_id).attributes.get("min") == 1.0
    assert hass.states.get(entity_id).attributes.get("max") == 100.0
    assert hass.states.get(entity_id).attributes.get("step") == 1.1
    assert hass.states.get(entity_id).attributes.get("icon") == "mdi:percent"
    assert hass.states.get(entity_id).attributes.get("unit_of_measurement") == "%"

    assert (
        hass.states.get(entity_id).attributes.get("friendly_name")
        == "FakeManufacturer FakeModel Number PWM1"
    )

    # change value from device
    await send_attributes_report(hass, cluster, {0x0055: 15})
    assert hass.states.get(entity_id).state == "15.0"

    # update value from device
    await send_attributes_report(hass, cluster, {0x0055: 20})
    assert hass.states.get(entity_id).state == "20.0"

    # change value from HA
    with patch(
        "zigpy.zcl.Cluster.write_attributes",
        return_value=[zcl_f.Status.SUCCESS, zcl_f.Status.SUCCESS],
    ):
        # set value via UI
        await hass.services.async_call(
            NUMBER_DOMAIN,
            "set_value",
            {"entity_id": entity_id, "value": 30.0},
            blocking=True,
        )
        assert cluster.write_attributes.mock_calls == [
            call({"present_value": 30.0}, manufacturer=None)
        ]
        cluster.PLUGGED_ATTR_READS["present_value"] = 30.0

    # update device value with failed attribute report
    cluster.PLUGGED_ATTR_READS["present_value"] = 40.0

    await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == "40.0"
    assert "present_value" in cluster.read_attributes.call_args[0][0]
