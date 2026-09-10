"""Test KNX entity suggestions generated from functional block semantics."""

from typing import Any

from homeassistant.components.knx.project import STORAGE_KEY as KNX_PROJECT_STORAGE_KEY
from homeassistant.components.knx.storage.entity_suggestions.functional_blocks import (
    _build_platform_suggestion,
    _collect_dpa_index,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import KNXTestKit

from tests.typing import WebSocketGenerator

DPT_SWITCH = {"main": 1, "sub": 1}
DPT_PERCENT = {"main": 5, "sub": 1}
DPT_COLOR_TEMP_ABS = {"main": 7, "sub": 600}
DPT_COLOR_RGB = {"main": 232, "sub": 600}


def _channel(name: str, fbs: list[str] | None, com_object_ids: list[str]) -> dict:
    return {
        "identifier": name,
        "name": name,
        "communication_object_ids": com_object_ids,
        "functional_blocks": fbs,
    }


def _com_object(dpas: list[str] | None, ga_links: list[str]) -> dict:
    return {"dpas": dpas, "group_address_links": ga_links}


def _group_address(address: str, dpt: dict | None) -> dict:
    return {"name": f"GA {address}", "address": address, "description": "", "dpt": dpt}


TEST_PROJECT_INFO = {
    "xknxproject_version": "3.9.0",
    "group_address_style": "ThreeLevel",
}

TEST_PROJECT: dict[str, Any] = {
    "info": TEST_PROJECT_INFO,
    "group_addresses": {
        "1/0/1": _group_address("1/0/1", DPT_SWITCH),
        "1/0/2": _group_address("1/0/2", DPT_SWITCH),
        "1/0/3": _group_address("1/0/3", DPT_SWITCH),
        "1/0/4": _group_address("1/0/4", DPT_SWITCH),
        "1/0/5": _group_address("1/0/5", DPT_PERCENT),  # wrong DPT for a switch GA
        "2/0/1": _group_address("2/0/1", DPT_SWITCH),
        "2/0/2": _group_address("2/0/2", DPT_SWITCH),
        "2/0/3": _group_address("2/0/3", DPT_PERCENT),
        "2/0/4": _group_address("2/0/4", DPT_PERCENT),
        "2/0/5": _group_address("2/0/5", DPT_PERCENT),
        "2/0/6": _group_address("2/0/6", DPT_PERCENT),
        "2/0/7": _group_address("2/0/7", DPT_SWITCH),
        "5/0/1": _group_address("5/0/1", DPT_SWITCH),
        "5/0/2": _group_address("5/0/2", DPT_SWITCH),
        "5/0/3": _group_address("5/0/3", DPT_PERCENT),
        "5/0/4": _group_address("5/0/4", DPT_PERCENT),
        "5/0/5": _group_address("5/0/5", DPT_COLOR_TEMP_ABS),
        "5/0/6": _group_address("5/0/6", DPT_COLOR_TEMP_ABS),
        "6/0/1": _group_address("6/0/1", DPT_SWITCH),
        "6/0/2": _group_address("6/0/2", DPT_SWITCH),
        "6/0/3": _group_address("6/0/3", DPT_COLOR_RGB),
        "6/0/4": _group_address("6/0/4", DPT_COLOR_RGB),
        "6/1/1": _group_address("6/1/1", DPT_PERCENT),
        "6/1/2": _group_address("6/1/2", DPT_PERCENT),
        "6/1/3": _group_address("6/1/3", DPT_PERCENT),
        "6/1/4": _group_address("6/1/4", DPT_PERCENT),
        "6/1/5": _group_address("6/1/5", DPT_PERCENT),
        "6/1/6": _group_address("6/1/6", DPT_PERCENT),
    },
    "devices": {
        "1.1.1": {
            "name": "Schaltaktor",
            "channels": {
                # channel ids are only unique within a device - colliding on purpose
                "CH-1": _channel(
                    "Ausgang 1", ["417"], ["co-1", "co-2", "co-4", "co-missing"]
                ),
                "CH-2": _channel("Ausgang 2", ["417"], ["co-3"]),
                "CH-3": _channel("Unsupported FB", ["999"], []),
                "CH-4": _channel("No semantics", None, ["co-1"]),
            },
        },
        "1.1.2": {
            "name": "Jalousieaktor",
            "channels": {
                "CH-1": _channel(
                    "Jalousie 1",
                    ["800"],
                    ["co-10", "co-11", "co-12", "co-13", "co-14", "co-15", "co-16"],
                ),
            },
        },
        "1.1.3": {
            "name": "Schaltaktor 2",
            "channels": {
                # same channel name as 1.1.1 CH-1 - names get device name prefixed
                "CH-1": _channel("Ausgang 1", ["417"], ["co-20"]),
                # write GA has non-matching DPT - no valid suggestion
                "CH-2": _channel("Wrong DPT", ["417"], ["co-21"]),
            },
        },
        "1.2.1": {
            "name": "TW Aktor",
            "channels": {
                "CH-1": _channel(
                    "Tunable White",
                    ["427"],
                    ["co-50", "co-51", "co-52", "co-53", "co-54", "co-55"],
                ),
            },
        },
        "1.2.2": {
            "name": "RGB Aktor",
            "channels": {
                # com objects for combined AND individual colour addresses
                "CH-1": _channel(
                    "RGB",
                    ["423"],
                    [
                        "co-60",
                        "co-61",
                        "co-62",
                        "co-63",
                        "co-70",
                        "co-71",
                        "co-72",
                        "co-73",
                        "co-74",
                        "co-75",
                    ],
                ),
            },
        },
    },
    "communication_objects": {
        "co-1": _com_object(["417.52"], ["1/0/1", "1/0/2"]),
        "co-2": _com_object(["417.51"], ["1/0/3"]),
        "co-3": _com_object(["417.52"], ["1/0/4"]),
        "co-4": _com_object(["417.69"], ["1/0/4"]),  # no config key for this DPA
        "co-10": _com_object(["800.81"], ["2/0/1"]),
        "co-11": _com_object(["800.82"], ["2/0/2"]),
        "co-12": _com_object(["800.71"], ["2/0/3"]),
        "co-13": _com_object(["800.85"], ["2/0/4"]),
        "co-14": _com_object(["800.72"], ["2/0/5"]),
        "co-15": _com_object(["800.56"], ["2/0/6"]),
        "co-16": _com_object(["800.75", "800.51"], ["2/0/7"]),
        "co-20": _com_object(["417.52"], ["1/0/1"]),
        "co-21": _com_object(["417.52"], ["1/0/5"]),
        "co-50": _com_object(["427.62"], ["5/0/1"]),
        "co-51": _com_object(["427.51"], ["5/0/2"]),
        "co-52": _com_object(["427.70"], ["5/0/3"]),
        "co-53": _com_object(["427.52"], ["5/0/4"]),
        "co-54": _com_object(["427.81"], ["5/0/5"]),
        "co-55": _com_object(["427.75"], ["5/0/6"]),
        "co-60": _com_object(["423.51"], ["6/0/1"]),
        "co-61": _com_object(["423.80"], ["6/0/2"]),
        "co-62": _com_object(["423.52"], ["6/0/3"]),
        "co-63": _com_object(["423.81"], ["6/0/4"]),
        "co-70": _com_object(["423.58"], ["6/1/1"]),
        "co-71": _com_object(["423.83"], ["6/1/2"]),
        "co-72": _com_object(["423.61"], ["6/1/3"]),
        "co-73": _com_object(["423.84"], ["6/1/4"]),
        "co-74": _com_object(["423.64"], ["6/1/5"]),
        "co-75": _com_object(["423.85"], ["6/1/6"]),
    },
}


def _test_channel(device: str, channel: str) -> dict:
    return TEST_PROJECT["devices"][device]["channels"][channel]


def test_collect_dpa_index() -> None:
    """Test DPA index generation from entity store schemas."""
    light_index = _collect_dpa_index(Platform.LIGHT)
    target = light_index["417.52"]
    assert target.path == ("ga_switch",)
    assert target.slot == "write"
    assert target.group_select is None

    target = light_index["418.51"]
    assert target.path == ("ga_switch",)
    assert target.slot == "state"

    # group select options are tracked with their option index
    target = light_index["423.52"]
    assert target.path == ("color", "ga_color")
    assert target.slot == "write"
    assert target.group_select == (("color",), 0)

    target = light_index["423.84"]
    assert target.path == ("color", "ga_green_brightness")
    assert target.slot == "state"
    assert target.group_select == (("color",), 1)

    assert "999.99" not in light_index


def test_switch_and_light_suggestion() -> None:
    """Test FB 417 suggestions with state, passive and unmatched DPAs."""
    channel = _test_channel("1.1.1", "CH-1")
    for platform in (Platform.LIGHT, Platform.SWITCH):
        suggestion = _build_platform_suggestion(
            TEST_PROJECT, channel, _collect_dpa_index(platform)
        )
        assert suggestion is not None
        assert suggestion["knx"] == {
            "ga_switch": {"write": "1/0/1", "state": "1/0/3", "passive": ["1/0/2"]}
        }
        # missing com objects are skipped; DPAs without config key are reported
        assert suggestion["unmatched_dpas"] == ["417.69"]
        # group addresses carry their project name
        assert suggestion["matched_group_addresses"] == [
            {"address": "1/0/1", "name": "GA 1/0/1"},
            {"address": "1/0/2", "name": "GA 1/0/2"},
            {"address": "1/0/3", "name": "GA 1/0/3"},
        ]


def test_cover_suggestion() -> None:
    """Test FB 800 suggestion."""
    channel = _test_channel("1.1.2", "CH-1")
    suggestion = _build_platform_suggestion(
        TEST_PROJECT, channel, _collect_dpa_index(Platform.COVER)
    )
    assert suggestion is not None
    assert suggestion["knx"] == {
        "ga_up_down": {"write": "2/0/1"},
        "ga_step": {"write": "2/0/2"},
        "ga_position_set": {"write": "2/0/3"},
        "ga_position_state": {"state": "2/0/4"},
        "ga_angle": {"write": "2/0/5", "state": "2/0/6"},
    }
    assert suggestion["unmatched_dpas"] == ["800.51", "800.75"]


def test_invalid_dpt_dropped() -> None:
    """Test that a write GA with non-matching DPT yields no suggestion."""
    channel = _test_channel("1.1.3", "CH-2")
    assert (
        _build_platform_suggestion(
            TEST_PROJECT, channel, _collect_dpa_index(Platform.SWITCH)
        )
        is None
    )


def test_tunable_white_suggestion() -> None:
    """Test FB 427 suggestion with `dpt` derived from the group address."""
    channel = _test_channel("1.2.1", "CH-1")
    suggestion = _build_platform_suggestion(
        TEST_PROJECT, channel, _collect_dpa_index(Platform.LIGHT)
    )
    assert suggestion is not None
    assert suggestion["knx"] == {
        "ga_switch": {"write": "5/0/1", "state": "5/0/2"},
        "ga_brightness": {"write": "5/0/3", "state": "5/0/4"},
        "ga_color_temp": {"write": "5/0/5", "state": "5/0/6", "dpt": "7.600"},
    }


def test_combined_color_preferred() -> None:
    """Test that the first matched group select option wins."""
    channel = _test_channel("1.2.2", "CH-1")
    suggestion = _build_platform_suggestion(
        TEST_PROJECT, channel, _collect_dpa_index(Platform.LIGHT)
    )
    assert suggestion is not None
    assert suggestion["knx"] == {
        "ga_switch": {"write": "6/0/1", "state": "6/0/2"},
        "color": {"ga_color": {"write": "6/0/3", "state": "6/0/4", "dpt": "232.600"}},
    }
    # individual colour DPAs were dropped in favor of the combined option
    assert suggestion["unmatched_dpas"] == [
        "423.58",
        "423.61",
        "423.64",
        "423.83",
        "423.84",
        "423.85",
    ]
    assert "6/1/1" not in [
        ga["address"] for ga in suggestion["matched_group_addresses"]
    ]


def test_individual_color_without_combined() -> None:
    """Test individual colour addresses are used when no combined com objects exist."""
    channel = _channel(
        "RGB einzeln",
        ["423"],
        ["co-60", "co-61", "co-70", "co-71", "co-72", "co-73", "co-74", "co-75"],
    )
    suggestion = _build_platform_suggestion(
        TEST_PROJECT, channel, _collect_dpa_index(Platform.LIGHT)
    )
    assert suggestion is not None
    assert suggestion["knx"] == {
        "ga_switch": {"write": "6/0/1", "state": "6/0/2"},
        "color": {
            "ga_red_brightness": {"write": "6/1/1", "state": "6/1/2"},
            "ga_green_brightness": {"write": "6/1/3", "state": "6/1/4"},
            "ga_blue_brightness": {"write": "6/1/5", "state": "6/1/6"},
        },
    }


async def _get_suggestions(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, **filters: Any
) -> dict:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "knx/get_entity_suggestions"} | filters,
    )
    res = await client.receive_json()
    assert res["success"], res
    return res["result"]


async def test_ws_get_entity_suggestions(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test the knx/get_entity_suggestions command."""
    hass_storage[KNX_PROJECT_STORAGE_KEY] = {"version": 1, "data": TEST_PROJECT}
    await knx.setup_integration()
    result = await _get_suggestions(hass, hass_ws_client)

    assert result["providers"]["fb"] == {
        "state": "ok",
        "functional_blocks_found": ["417", "423", "427", "800", "999"],
    }
    suggestions = {suggestion["id"]: suggestion for suggestion in result["suggestions"]}
    assert sorted(suggestions) == [
        "fb_1.1.1_CH-1",
        "fb_1.1.1_CH-2",
        "fb_1.1.2_CH-1",
        "fb_1.1.3_CH-1",
        "fb_1.2.1_CH-1",
        "fb_1.2.2_CH-1",
    ]

    switch_actuator = suggestions["fb_1.1.1_CH-1"]
    assert switch_actuator["source"] == "fb"
    assert switch_actuator["group_id"] == "1.1.1"
    assert switch_actuator["group_name"] == "Schaltaktor"
    assert switch_actuator["metadata"] == {"functional_blocks": ["417"]}
    assert switch_actuator["secondary_info"] == "Ausgang 1"
    # light is the default for FB 417
    assert switch_actuator["platform_options"] == ["light", "switch"]
    assert (
        switch_actuator["suggestions"]["light"]["knx"]["ga_switch"]["write"] == "1/0/1"
    )
    assert switch_actuator["existing_entity_ids"] == []

    # ambiguous channel names get the device name prefixed
    assert switch_actuator["suggested_name"] == "Schaltaktor Ausgang 1"
    assert suggestions["fb_1.1.3_CH-1"]["suggested_name"] == ("Schaltaktor 2 Ausgang 1")
    assert suggestions["fb_1.1.1_CH-2"]["suggested_name"] == "Ausgang 2"

    assert suggestions["fb_1.1.2_CH-1"]["platform_options"] == ["cover"]


async def test_ws_get_entity_suggestions_duplicates(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test that entities using suggested group addresses are reported."""
    hass_storage[KNX_PROJECT_STORAGE_KEY] = {"version": 1, "data": TEST_PROJECT}
    await knx.setup_integration()
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "knx/create_entity",
            "platform": Platform.SWITCH,
            "data": {
                "entity": {
                    "name": "Existing",
                    "device_info": None,
                    "entity_category": None,
                },
                "knx": {"ga_switch": {"write": "1/0/4"}},
            },
        }
    )
    res = await client.receive_json()
    assert res["success"], res
    entity_id = res["result"]["entity_id"]

    result = await _get_suggestions(hass, hass_ws_client)
    suggestions = {suggestion["id"]: suggestion for suggestion in result["suggestions"]}
    assert suggestions["fb_1.1.1_CH-2"]["existing_entity_ids"] == [entity_id]
    assert suggestions["fb_1.1.2_CH-1"]["existing_entity_ids"] == []


async def test_ws_get_entity_suggestions_no_project(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test suggestions without project data."""
    await knx.setup_integration()
    result = await _get_suggestions(hass, hass_ws_client)
    assert result["suggestions"] == []
    assert result["providers"]["fb"] == {"state": "no_project"}


async def test_ws_get_entity_suggestions_outdated_parser(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test suggestions for a project imported with an old parser version."""
    hass_storage[KNX_PROJECT_STORAGE_KEY] = {
        "version": 1,
        "data": {
            **TEST_PROJECT,
            "info": {**TEST_PROJECT_INFO, "xknxproject_version": "3.8.0"},
        },
    }
    await knx.setup_integration()
    result = await _get_suggestions(hass, hass_ws_client)
    assert result["suggestions"] == []
    assert result["providers"]["fb"] == {
        "state": "outdated_parser",
        "parser_version": "3.8.0",
    }


async def test_ws_get_entity_suggestions_no_semantics(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test suggestions for a project without semantics information."""
    hass_storage[KNX_PROJECT_STORAGE_KEY] = {
        "version": 1,
        "data": {
            "info": TEST_PROJECT_INFO,
            "group_addresses": {},
            "devices": {
                "1.1.1": {
                    "name": "Aktor",
                    "channels": {"CH-1": _channel("Ausgang", None, [])},
                }
            },
            "communication_objects": {},
        },
    }
    await knx.setup_integration()
    result = await _get_suggestions(hass, hass_ws_client)
    assert result["suggestions"] == []
    assert result["providers"]["fb"] == {"state": "no_semantics"}
