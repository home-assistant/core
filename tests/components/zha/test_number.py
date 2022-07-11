"""Test zha analog output."""
from unittest.mock import call, patch

import pytest
from zigpy.exceptions import ZigbeeException
from zigpy.profiles import zha
import zigpy.zcl.clusters.general as general
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.const import ENTITY_CATEGORY_CONFIG, STATE_UNAVAILABLE, Platform
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .common import (
    async_enable_traffic,
    async_test_rejoin,
    find_entity_id,
    send_attributes_report,
    update_attribute_cache,
)
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

from tests.common import mock_coro


@pytest.fixture(autouse=True)
def number_platform_only():
    """Only setup the number and required base platforms to speed up tests."""
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


@pytest.fixture
def zigpy_analog_output_device(zigpy_device_mock):
    """Zigpy analog_output device."""

    endpoints = {
        1: {
            SIG_EP_TYPE: zha.DeviceType.LEVEL_CONTROL_SWITCH,
            SIG_EP_INPUT: [general.AnalogOutput.cluster_id, general.Basic.cluster_id],
            SIG_EP_OUTPUT: [],
        }
    }
    return zigpy_device_mock(endpoints)


@pytest.fixture
async def light(zigpy_device_mock):
    """Siren fixture."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_PROFILE: zha.PROFILE_ID,
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_LIGHT,
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    general.Identify.cluster_id,
                    general.OnOff.cluster_id,
                    general.LevelControl.cluster_id,
                ],
                SIG_EP_OUTPUT: [general.Ota.cluster_id],
            }
        },
        node_descriptor=b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00",
    )

    return zigpy_device


async def test_number(hass, zha_device_joined_restored, zigpy_analog_output_device):
    """Test zha number platform."""

    cluster = zigpy_analog_output_device.endpoints.get(1).analog_output
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

    zha_device = await zha_device_joined_restored(zigpy_analog_output_device)
    # one for present_value and one for the rest configuration attributes
    assert cluster.read_attributes.call_count == 3
    attr_reads = set()
    for call_args in cluster.read_attributes.call_args_list:
        attr_reads |= set(call_args[0][0])
    assert "max_present_value" in attr_reads
    assert "min_present_value" in attr_reads
    assert "relinquish_default" in attr_reads
    assert "resolution" in attr_reads
    assert "description" in attr_reads
    assert "engineering_units" in attr_reads
    assert "application_type" in attr_reads

    entity_id = await find_entity_id(Platform.NUMBER, zha_device, hass)
    assert entity_id is not None

    await async_enable_traffic(hass, [zha_device], enabled=False)
    # test that the number was created and that it is unavailable
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # allow traffic to flow through the gateway and device
    assert cluster.read_attributes.call_count == 3
    await async_enable_traffic(hass, [zha_device])
    await hass.async_block_till_done()
    assert cluster.read_attributes.call_count == 6

    # test that the state has changed from unavailable to 15.0
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
    assert cluster.read_attributes.call_count == 6
    await send_attributes_report(hass, cluster, {0x0055: 15})
    assert hass.states.get(entity_id).state == "15.0"

    # update value from device
    await send_attributes_report(hass, cluster, {0x0055: 20})
    assert hass.states.get(entity_id).state == "20.0"

    # change value from HA
    with patch(
        "zigpy.zcl.Cluster.write_attributes",
        return_value=mock_coro([zcl_f.Status.SUCCESS, zcl_f.Status.SUCCESS]),
    ):
        # set value via UI
        await hass.services.async_call(
            NUMBER_DOMAIN,
            "set_value",
            {"entity_id": entity_id, "value": 30.0},
            blocking=True,
        )
        assert len(cluster.write_attributes.mock_calls) == 1
        assert cluster.write_attributes.call_args == call({"present_value": 30.0})
        cluster.PLUGGED_ATTR_READS["present_value"] = 30.0

    # test rejoin
    assert cluster.read_attributes.call_count == 6
    await async_test_rejoin(hass, zigpy_analog_output_device, [cluster], (1,))
    assert hass.states.get(entity_id).state == "30.0"
    assert cluster.read_attributes.call_count == 9

    # update device value with failed attribute report
    cluster.PLUGGED_ATTR_READS["present_value"] = 40.0
    # validate the entity still contains old value
    assert hass.states.get(entity_id).state == "30.0"

    await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == "40.0"
    assert cluster.read_attributes.call_count == 10
    assert "present_value" in cluster.read_attributes.call_args[0][0]


@pytest.mark.parametrize(
    "attr, initial_value, new_value",
    (
        ("on_off_transition_time", 20, 5),
        ("on_level", 255, 50),
        ("on_transition_time", 5, 1),
        ("off_transition_time", 5, 1),
        ("default_move_rate", 1, 5),
        ("start_up_current_level", 254, 125),
    ),
)
async def test_level_control_number(
    hass, light, zha_device_joined, attr, initial_value, new_value
):
    """Test zha level control number entities - new join."""

    entity_registry = er.async_get(hass)
    level_control_cluster = light.endpoints[1].level
    level_control_cluster.PLUGGED_ATTR_READS = {
        attr: initial_value,
    }
    zha_device = await zha_device_joined(light)

    entity_id = await find_entity_id(
        Platform.NUMBER,
        zha_device,
        hass,
        qualifier=attr.replace("_", ""),
    )
    assert entity_id is not None

    assert level_control_cluster.read_attributes.call_count == 3
    assert (
        call(
            [
                "on_off_transition_time",
                "on_level",
                "on_transition_time",
                "off_transition_time",
                "default_move_rate",
            ],
            allow_cache=True,
            only_cache=False,
            manufacturer=None,
        )
        in level_control_cluster.read_attributes.call_args_list
    )

    assert (
        call(
            ["start_up_current_level"],
            allow_cache=True,
            only_cache=False,
            manufacturer=None,
        )
        in level_control_cluster.read_attributes.call_args_list
    )

    assert (
        call(
            [
                "current_level",
            ],
            allow_cache=False,
            only_cache=False,
            manufacturer=None,
        )
        in level_control_cluster.read_attributes.call_args_list
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == str(initial_value)

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.entity_category == ENTITY_CATEGORY_CONFIG

    # Test number set_value
    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": entity_id,
            "value": new_value,
        },
        blocking=True,
    )

    assert level_control_cluster.write_attributes.call_count == 1
    assert level_control_cluster.write_attributes.call_args[0][0] == {
        attr: new_value,
    }

    state = hass.states.get(entity_id)
    assert state
    assert state.state == str(new_value)

    level_control_cluster.read_attributes.reset_mock()
    await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    # the mocking doesn't update the attr cache so this flips back to initial value
    assert hass.states.get(entity_id).state == str(initial_value)
    assert level_control_cluster.read_attributes.call_count == 1
    assert (
        call(
            [
                attr,
            ],
            allow_cache=False,
            only_cache=False,
            manufacturer=None,
        )
        in level_control_cluster.read_attributes.call_args_list
    )

    level_control_cluster.write_attributes.reset_mock()
    level_control_cluster.write_attributes.side_effect = ZigbeeException

    await hass.services.async_call(
        "number",
        "set_value",
        {
            "entity_id": entity_id,
            "value": new_value,
        },
        blocking=True,
    )

    assert level_control_cluster.write_attributes.call_count == 1
    assert level_control_cluster.write_attributes.call_args[0][0] == {
        attr: new_value,
    }
    assert hass.states.get(entity_id).state == str(initial_value)
