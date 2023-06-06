"""Tests for ZHA helpers."""
import logging
from unittest.mock import patch

import pytest
import voluptuous_serialize
import zigpy.profiles.zha as zha
from zigpy.types.basic import uint16_t
import zigpy.zcl.clusters.general as general
import zigpy.zcl.clusters.lighting as lighting

from homeassistant.components.zha.core.helpers import (
    cluster_command_schema_to_vol_schema,
    convert_to_zcl_values,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .common import async_enable_traffic
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

_LOGGER = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def light_platform_only():
    """Only set up the light and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.BUTTON,
            Platform.LIGHT,
            Platform.NUMBER,
            Platform.SELECT,
        ),
    ):
        yield


@pytest.fixture
async def device_light(hass, zigpy_device_mock, zha_device_joined):
    """Test light."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.OnOff.cluster_id,
                    general.LevelControl.cluster_id,
                    lighting.Color.cluster_id,
                    general.Groups.cluster_id,
                    general.Identify.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.COLOR_DIMMABLE_LIGHT,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        }
    )
    color_cluster = zigpy_device.endpoints[1].light_color
    color_cluster.PLUGGED_ATTR_READS = {
        "color_capabilities": lighting.Color.ColorCapabilities.Color_temperature
        | lighting.Color.ColorCapabilities.XY_attributes
    }
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.available = True
    return color_cluster, zha_device


async def test_zcl_schema_conversions(hass: HomeAssistant, device_light) -> None:
    """Test ZHA ZCL schema conversion helpers."""
    color_cluster, zha_device = device_light
    await async_enable_traffic(hass, [zha_device])
    command_schema = color_cluster.commands_by_name["color_loop_set"].schema
    expected_schema = [
        {
            "type": "multi_select",
            "options": ["Action", "Direction", "Time", "Start Hue"],
            "name": "update_flags",
            "required": True,
        },
        {
            "type": "select",
            "options": [
                ("Deactivate", "Deactivate"),
                ("Activate from color loop hue", "Activate from color loop hue"),
                ("Activate from current hue", "Activate from current hue"),
            ],
            "name": "action",
            "required": True,
        },
        {
            "type": "select",
            "options": [("Decrement", "Decrement"), ("Increment", "Increment")],
            "name": "direction",
            "required": True,
        },
        {
            "type": "integer",
            "valueMin": 0,
            "valueMax": 65535,
            "name": "time",
            "required": True,
        },
        {
            "type": "integer",
            "valueMin": 0,
            "valueMax": 65535,
            "name": "start_hue",
            "required": True,
        },
        {
            "type": "integer",
            "valueMin": 0,
            "valueMax": 255,
            "name": "options_mask",
            "optional": True,
        },
        {
            "type": "integer",
            "valueMin": 0,
            "valueMax": 255,
            "name": "options_override",
            "optional": True,
        },
    ]
    vol_schema = voluptuous_serialize.convert(
        cluster_command_schema_to_vol_schema(command_schema),
        custom_serializer=cv.custom_serializer,
    )
    assert vol_schema == expected_schema

    raw_data = {
        "update_flags": ["Action", "Start Hue"],
        "action": "Activate from current hue",
        "direction": "Increment",
        "time": 20,
        "start_hue": 196,
    }

    converted_data = convert_to_zcl_values(raw_data, command_schema)

    assert isinstance(
        converted_data["update_flags"], lighting.Color.ColorLoopUpdateFlags
    )
    assert lighting.Color.ColorLoopUpdateFlags.Action in converted_data["update_flags"]
    assert (
        lighting.Color.ColorLoopUpdateFlags.Start_Hue in converted_data["update_flags"]
    )

    assert isinstance(converted_data["action"], lighting.Color.ColorLoopAction)
    assert (
        converted_data["action"]
        == lighting.Color.ColorLoopAction.Activate_from_current_hue
    )

    assert isinstance(converted_data["direction"], lighting.Color.ColorLoopDirection)
    assert converted_data["direction"] == lighting.Color.ColorLoopDirection.Increment

    assert isinstance(converted_data["time"], uint16_t)
    assert converted_data["time"] == 20

    assert isinstance(converted_data["start_hue"], uint16_t)
    assert converted_data["start_hue"] == 196

    raw_data = {
        "update_flags": [0b0000_0001, 0b0000_1000],
        "action": 0x02,
        "direction": 0x01,
        "time": 20,
        "start_hue": 196,
    }

    converted_data = convert_to_zcl_values(raw_data, command_schema)

    assert isinstance(
        converted_data["update_flags"], lighting.Color.ColorLoopUpdateFlags
    )
    assert lighting.Color.ColorLoopUpdateFlags.Action in converted_data["update_flags"]
    assert (
        lighting.Color.ColorLoopUpdateFlags.Start_Hue in converted_data["update_flags"]
    )

    assert isinstance(converted_data["action"], lighting.Color.ColorLoopAction)
    assert (
        converted_data["action"]
        == lighting.Color.ColorLoopAction.Activate_from_current_hue
    )

    assert isinstance(converted_data["direction"], lighting.Color.ColorLoopDirection)
    assert converted_data["direction"] == lighting.Color.ColorLoopDirection.Increment

    assert isinstance(converted_data["time"], uint16_t)
    assert converted_data["time"] == 20

    assert isinstance(converted_data["start_hue"], uint16_t)
    assert converted_data["start_hue"] == 196

    # This time, the update flags bitmap is empty
    raw_data = {
        "update_flags": [],
        "action": 0x02,
        "direction": 0x01,
        "time": 20,
        "start_hue": 196,
    }

    converted_data = convert_to_zcl_values(raw_data, command_schema)

    # No flags are passed through
    assert converted_data["update_flags"] == 0
