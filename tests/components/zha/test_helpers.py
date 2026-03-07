"""Tests for ZHA helpers."""

from collections.abc import Callable, Coroutine
import logging
from typing import Any
from unittest.mock import MagicMock

import pytest
import voluptuous_serialize
from zigpy.application import ControllerApplication
from zigpy.types.basic import uint16_t
from zigpy.zcl.clusters import lighting

from homeassistant.components.zha import const as zha_const
from homeassistant.components.zha.helpers import (
    ZHAGroupProxy,
    cluster_command_schema_to_vol_schema,
    convert_to_zcl_values,
    create_zha_config,
    exclude_none_values,
    get_zha_data,
    get_zha_gateway_proxy,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import FIXTURE_GRP_ID, FIXTURE_GRP_NAME

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_zcl_schema_conversions(hass: HomeAssistant) -> None:
    """Test ZHA ZCL schema conversion helpers."""
    command_schema = lighting.Color.ServerCommandDefs.color_loop_set.schema
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
            "type": "multi_select",
            "options": ["Execute if off present"],
            "name": "options_mask",
            "optional": True,
            "required": False,
        },
        {
            "type": "multi_select",
            "options": ["Execute if off"],
            "name": "options_override",
            "optional": True,
            "required": False,
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


@pytest.mark.parametrize(
    ("obj", "expected_output"),
    [
        ({"a": 1, "b": 2, "c": None}, {"a": 1, "b": 2}),
        ({"a": 1, "b": 2, "c": 0}, {"a": 1, "b": 2, "c": 0}),
        ({"a": 1, "b": 2, "c": ""}, {"a": 1, "b": 2, "c": ""}),
        ({"a": 1, "b": 2, "c": False}, {"a": 1, "b": 2, "c": False}),
    ],
)
def test_exclude_none_values(
    obj: dict[str, Any], expected_output: dict[str, Any]
) -> None:
    """Test exclude_none_values helper."""
    result = exclude_none_values(obj)
    assert result == expected_output

    for key, value in expected_output.items():
        assert value == obj[key]


async def test_create_zha_config_remove_unused(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_zigpy_connect: ControllerApplication,
) -> None:
    """Test creating ZHA config data with unused keys."""
    config_entry.add_to_hass(hass)

    options = config_entry.options.copy()
    options["custom_configuration"]["zha_options"]["some_random_key"] = "a value"

    hass.config_entries.async_update_entry(config_entry, options=options)

    assert (
        config_entry.options["custom_configuration"]["zha_options"]["some_random_key"]
        == "a value"
    )

    status = await async_setup_component(
        hass,
        zha_const.DOMAIN,
        {zha_const.DOMAIN: {zha_const.CONF_ENABLE_QUIRKS: False}},
    )
    assert status is True
    await hass.async_block_till_done()

    ha_zha_data = get_zha_data(hass)

    # Does not error out
    create_zha_config(hass, ha_zha_data)


@pytest.mark.parametrize(
    ("group_id", "expected_identifier"),
    [
        (0x0001, "zha_group_0x0001"),
        (0x1001, "zha_group_0x1001"),
        (0xFFFF, "zha_group_0xffff"),
    ],
)
def test_zha_group_proxy_group_device_identifier(
    group_id: int, expected_identifier: str
) -> None:
    """Test ZHAGroupProxy group_device_identifier property."""
    group_proxy = ZHAGroupProxy(MagicMock(group_id=group_id), MagicMock())
    assert group_proxy.group_device_identifier == expected_identifier


def test_zha_group_proxy_get_device_info() -> None:
    """Test ZHAGroupProxy get_device_info returns correct DeviceInfo."""
    mock_group = MagicMock(group_id=0x1001)
    mock_group.name = "Test Group"
    coordinator_ieee = "00:15:8d:00:02:32:4f:32"

    device_info = ZHAGroupProxy(mock_group, MagicMock()).get_device_info(
        coordinator_ieee
    )

    assert device_info == {
        "identifiers": {(zha_const.DOMAIN, "zha_group_0x1001")},
        "name": "Test Group",
        "manufacturer": "Zigbee",
        "model": "Group",
        "entry_type": dr.DeviceEntryType.SERVICE,
        "via_device": (zha_const.DOMAIN, coordinator_ieee),
    }


def test_zha_group_proxy_device_id_property() -> None:
    """Test ZHAGroupProxy device_id property getter and setter."""
    group_proxy = ZHAGroupProxy(MagicMock(group_id=0x1001), MagicMock())

    assert group_proxy.device_id is None
    group_proxy.device_id = "test_device_id"
    assert group_proxy.device_id == "test_device_id"


async def test_zha_group_proxy_no_device_for_group_without_entities(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[Any, Any, None]],
) -> None:
    """Test that no device is created for groups without entities."""
    await setup_zha()

    gateway_proxy = get_zha_gateway_proxy(hass)

    group_proxy = gateway_proxy.group_proxies.get(FIXTURE_GRP_ID)
    assert group_proxy is not None
    assert group_proxy.group.name == FIXTURE_GRP_NAME
    # Fixture group has no members, so no entities, so no device
    assert not group_proxy.group.group_entities
    assert group_proxy.device_id is None
