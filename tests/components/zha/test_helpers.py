"""Tests for ZHA helpers."""

import asyncio
from collections.abc import Callable, Coroutine
import logging
from typing import Any

from probatio import to_field_list
import pytest
from zha.application.const import ATTR_TYPE, ZHA_GW_MSG
from zigpy.application import ControllerApplication
from zigpy.types.basic import uint16_t
from zigpy.zcl.clusters import lighting

from homeassistant.components.zha import const as zha_const
from homeassistant.components.zha.helpers import (
    ZHA_GW_MSG_LOG_ENTRY,
    ZHA_GW_MSG_LOG_OUTPUT,
    cluster_command_schema_to_vol_schema,
    convert_to_zcl_values,
    create_zha_config,
    exclude_none_values,
    get_zha_data,
    get_zha_gateway_proxy,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import async_setup_component

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
    vol_schema = to_field_list(
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


async def test_debug_mode_log_filter(
    hass: HomeAssistant, setup_zha: Callable[..., Coroutine[None]]
) -> None:
    """Test a debug mode session filters relayed logs only until it ends."""
    await setup_zha()
    gateway_proxy = get_zha_gateway_proxy(hass)

    relayed: list[str] = []
    marker_relayed = asyncio.Event()

    @callback
    def collect(data: dict[str, Any]) -> None:
        if data[ATTR_TYPE] != ZHA_GW_MSG_LOG_OUTPUT:
            return
        message = data[ZHA_GW_MSG_LOG_ENTRY]["message"][0]
        if message.startswith("test "):
            relayed.append(message)
        if message == "test marker":
            marker_relayed.set()

    unsub = async_dispatcher_connect(hass, ZHA_GW_MSG, collect)

    async def log_and_wait(*messages: str) -> None:
        # The relay is a queue, so the marker arrives after everything before it
        marker_relayed.clear()
        for message in (*messages, "test marker"):
            logging.getLogger("zha").debug(message)
        async with asyncio.timeout(5):
            await marker_relayed.wait()

    def drop_filtered(record: logging.LogRecord) -> bool:
        return record.getMessage() != "test filtered"

    gateway_proxy.async_enable_debug_mode(drop_filtered)
    await log_and_wait("test filtered", "test kept")
    gateway_proxy.async_disable_debug_mode(drop_filtered)
    assert relayed == ["test kept", "test marker"]

    # A later session without the filter relays everything again
    relayed.clear()
    gateway_proxy.async_enable_debug_mode()
    await log_and_wait("test filtered")
    gateway_proxy.async_disable_debug_mode()
    assert relayed == ["test filtered", "test marker"]

    unsub()
