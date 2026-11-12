"""Test KNX entity suggestions generated from building functions."""

from typing import Any

from homeassistant.components.knx.project import STORAGE_KEY as KNX_PROJECT_STORAGE_KEY
from homeassistant.components.knx.storage.entity_suggestions.functions import (
    _build_platform_suggestion,
    _function_roles,
)
from homeassistant.const import Platform

from . import KnxEntityGenerator, KnxSuggestionGetter
from .conftest import KNXTestKit

DPT_SWITCH = {"main": 1, "sub": 1}
DPT_UP_DOWN = {"main": 1, "sub": 8}
DPT_STEP = {"main": 1, "sub": 7}
DPT_PERCENT = {"main": 5, "sub": 1}
DPT_TEMPERATURE = {"main": 9, "sub": 1}
DPT_HVAC_MODE = {"main": 20, "sub": 102}
DPT_COUNTER = {"main": 5, "sub": 10}
DPT_PERCENT_ANY = {"main": 5, "sub": None}


def _group_address(address: str, dpt: dict[str, int] | None) -> dict[str, Any]:
    return {"name": f"GA {address}", "address": address, "description": "", "dpt": dpt}


def _function(
    name: str, function_type: str, space_id: str, *links: tuple[str, str]
) -> dict[str, Any]:
    return {
        "function_type": function_type,
        "group_addresses": {
            f"ref-{address}": {
                "address": address,
                "name": "",
                "project_uid": None,
                "role": role,
            }
            for address, role in links
        },
        "identifier": name,
        "name": name,
        "project_uid": None,
        "space_id": space_id,
        "usage_text": function_type,
    }


def _space(identifier: str, name: str, spaces: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Room" if not spaces else "Building",
        "identifier": identifier,
        "name": name,
        "usage_id": None,
        "usage_text": "",
        "number": "",
        "description": "",
        "project_uid": None,
        "devices": [],
        "spaces": spaces,
        "functions": [],
    }


TEST_PROJECT: dict[str, Any] = {
    "info": {"xknxproject_version": "3.10.0", "group_address_style": "ThreeLevel"},
    "group_addresses": {
        "1/0/1": _group_address("1/0/1", DPT_SWITCH),
        "1/0/2": _group_address("1/0/2", DPT_SWITCH),
        "1/0/3": _group_address("1/0/3", DPT_PERCENT),
        "1/0/4": _group_address("1/0/4", DPT_PERCENT),
        "2/0/1": _group_address("2/0/1", DPT_UP_DOWN),
        "2/0/2": _group_address("2/0/2", DPT_STEP),
        "2/0/3": _group_address("2/0/3", DPT_PERCENT),
        "3/0/1": _group_address("3/0/1", DPT_TEMPERATURE),
        "3/0/2": _group_address("3/0/2", DPT_TEMPERATURE),
        "3/0/3": _group_address("3/0/3", DPT_PERCENT),
        "3/0/4": _group_address("3/0/4", DPT_HVAC_MODE),
        "3/0/5": _group_address("3/0/5", DPT_SWITCH),
        "4/0/1": _group_address("4/0/1", DPT_SWITCH),
        "5/0/1": _group_address("5/0/1", DPT_COUNTER),
        "5/0/2": _group_address("5/0/2", DPT_PERCENT_ANY),
    },
    "devices": {},
    "communication_objects": {},
    "locations": {
        "P-1": _space(
            "P-1",
            "House",
            {
                "P-2": _space("P-2", "Kitchen", {}),
                "P-3": _space("P-3", "Living room", {}),
            },
        )
    },
    "functions": {
        # roles stored in the project
        "F-1": _function(
            "Ceiling",
            "FT-6",
            "P-2",
            ("1/0/1", "SwitchOnOff"),
            ("1/0/2", "InfoOnOff"),
            ("1/0/3", "DimmingValue"),
            ("1/0/4", "InfoDimmingValue"),
        ),
        # roles from the DPTs
        "F-2": _function(
            "Blind", "FT-7", "P-3", ("2/0/1", ""), ("2/0/2", ""), ("2/0/3", "")
        ),
        "F-3": _function(
            "Radiator",
            "FT-9",
            "P-3",
            ("3/0/1", "TempRoom"),
            ("3/0/2", "TempRoomSetpoint"),
            ("3/0/3", "ValvePosition"),
            ("3/0/4", "HVACMode"),
        ),
        "F-4": _function("Socket", "FT-10", "P-2", ("4/0/1", "SwitchOnOff")),
        # without its required setpoint, of a custom type, without addresses
        "F-5": _function("Floor heating", "FT-8", "P-2", ("3/0/1", "TempRoom")),
        "F-6": _function("Scene", "FT-0", "P-2", ("4/0/1", "")),
        "F-7": _function("Empty light", "FT-1", "P-9"),
    },
}


def test_roles_stored_or_from_the_dpt() -> None:
    """Test a stored role is kept and others follow their DPT."""
    project = TEST_PROJECT
    function = _function(
        "Light", "FT-6", "P-2", ("1/0/3", ""), ("1/0/1", ""), ("1/0/2", "InfoOnOff")
    )
    assert _function_roles(project, function) == {
        "InfoOnOff": "1/0/2",
        # the first free function point of the DPT
        "DimmingValue": "1/0/3",
        "SwitchOnOff": "1/0/1",
    }
    # a role of another type, and an address without DPT
    function = _function("Socket", "FT-10", "P-2", ("9/9/9", "MoveUpDown"))
    assert _function_roles(project, function) == {"SwitchOnOff": "9/9/9"}
    # no free function point is left
    function = _function(
        "Socket", "FT-10", "P-2", ("1/0/1", ""), ("1/0/2", ""), ("4/0/1", "")
    )
    assert _function_roles(project, function) == {
        "SwitchOnOff": "1/0/1",
        "InfoOnOff": "1/0/2",
    }


def test_second_address_of_a_stored_role() -> None:
    """Test a second address stored with a taken role is not given another role."""
    function = _function(
        "Light", "FT-1", "P-2", ("1/0/2", "InfoOnOff"), ("1/0/1", "InfoOnOff")
    )
    # a second status address doesn't become the switching command
    assert _function_roles(TEST_PROJECT, function) == {"InfoOnOff": "1/0/2"}
    assert _build_platform_suggestion(TEST_PROJECT, function) is None


def test_roles_fit_the_dpt() -> None:
    """Test group addresses only take function points their DPT fits."""
    # a count (5.010) is no brightness percentage (5.001); a main number fits
    function = _function("Light", "FT-6", "P-2", ("5/0/1", ""), ("5/0/2", ""))
    assert _function_roles(TEST_PROJECT, function) == {"DimmingValue": "5/0/2"}
    # a stored role whose DPT doesn't fit is not used
    function = _function(
        "Socket", "FT-10", "P-2", ("3/0/1", "SwitchOnOff"), ("1/0/2", "InfoOnOff")
    )
    assert _function_roles(TEST_PROJECT, function) == {"InfoOnOff": "1/0/2"}
    function = _function("Light", "FT-6", "P-2", ("5/0/1", "DimmingValue"))
    assert _function_roles(TEST_PROJECT, function) == {}


def _com_object(
    address: str, write: bool, communication: bool = True
) -> dict[str, Any]:
    return {
        "group_address_links": [address],
        "flags": {
            "read": not write,
            "write": write,
            "communication": communication,
            "transmit": not write,
            "update": False,
            "read_on_init": False,
        },
    }


def test_command_roles_need_a_writing_receiver() -> None:
    """Test a group address no linked object writes takes no command role."""
    project = {
        **TEST_PROJECT,
        "communication_objects": {
            # the actuator's status object only transmits 1/0/2
            "O-1": _com_object("1/0/2", write=False),
            "O-2": _com_object("1/0/1", write=True),
        },
    }
    # the status address comes first: it is no switching command
    function = _function("Light", "FT-1", "P-2", ("1/0/2", ""), ("1/0/1", ""))
    assert _function_roles(project, function) == {
        "InfoOnOff": "1/0/2",
        "SwitchOnOff": "1/0/1",
    }
    # stored as the command, but nothing receives it
    function = _function("Light", "FT-1", "P-2", ("1/0/2", "SwitchOnOff"))
    assert _function_roles(project, function) == {}
    assert _build_platform_suggestion(project, function) is None
    # without linked objects in the project, the receivers are unknown
    function = _function("Socket", "FT-10", "P-2", ("4/0/1", "SwitchOnOff"))
    assert _function_roles(project, function) == {"SwitchOnOff": "4/0/1"}
    # an object without the communication flag takes no part on the bus
    project["communication_objects"]["O-3"] = _com_object(
        "4/0/1", write=True, communication=False
    )
    assert _function_roles(project, function) == {}


def test_brightness_feedback_without_brightness_value() -> None:
    """Test a dimmable light without an absolute brightness value still switches."""
    function = _function(
        "Light",
        "FT-6",
        "P-2",
        ("1/0/1", "SwitchOnOff"),
        ("1/0/2", "InfoOnOff"),
        ("1/0/4", "InfoDimmingValue"),
    )
    platform, suggestion = _build_platform_suggestion(TEST_PROJECT, function)
    assert platform is Platform.LIGHT
    assert suggestion["knx"] == {
        "ga_switch": {"write": "1/0/1", "state": "1/0/2", "passive": []},
    }
    assert suggestion["unmatched"] == ["1/0/4"]


def test_dimmable_light() -> None:
    """Test a dimmable light with switching and brightness."""
    platform, suggestion = _build_platform_suggestion(
        TEST_PROJECT, TEST_PROJECT["functions"]["F-1"]
    )
    assert platform is Platform.LIGHT
    assert suggestion["knx"] == {
        "ga_switch": {"write": "1/0/1", "state": "1/0/2", "passive": []},
        "ga_brightness": {"write": "1/0/3", "state": "1/0/4", "passive": []},
    }
    assert [ga["address"] for ga in suggestion["matched_group_addresses"]] == [
        "1/0/1",
        "1/0/2",
        "1/0/3",
        "1/0/4",
    ]
    assert suggestion["unmatched"] == []


def test_sun_protection() -> None:
    """Test a cover from roles assigned by DPT."""
    platform, suggestion = _build_platform_suggestion(
        TEST_PROJECT, TEST_PROJECT["functions"]["F-2"]
    )
    assert platform is Platform.COVER
    assert suggestion["knx"]["ga_up_down"]["write"] == "2/0/1"
    assert suggestion["knx"]["ga_step"]["write"] == "2/0/2"
    # the first 5.001 point of sun protection is the blinds position
    assert suggestion["knx"]["ga_position_state"]["state"] == "2/0/3"


def test_heating() -> None:
    """Test a climate entity with its setpoint written and read on one address."""
    platform, suggestion = _build_platform_suggestion(
        TEST_PROJECT, TEST_PROJECT["functions"]["F-3"]
    )
    assert platform is Platform.CLIMATE
    knx = suggestion["knx"]
    assert knx["target_temperature"]["ga_temperature_target"] == {
        "write": "3/0/2",
        "state": "3/0/2",
        "passive": [],
    }
    assert knx["ga_temperature_current"]["state"] == "3/0/1"
    assert knx["ga_operation_mode"] == {
        "write": "3/0/4",
        "state": "3/0/4",
        "passive": [],
    }
    assert knx["ga_valve"]["state"] == "3/0/3"
    # a switching valve tells whether the room is heated
    function = _function(
        "Floor",
        "FT-8",
        "P-2",
        ("3/0/1", "TempRoom"),
        ("3/0/2", "TempRoomSetpoint"),
        ("3/0/5", "ValveSwitch"),
    )
    _platform, suggestion = _build_platform_suggestion(TEST_PROJECT, function)
    assert suggestion["knx"]["ga_active"]["state"] == "3/0/5"


def test_no_suggestion() -> None:
    """Test functions without an entity."""
    functions = TEST_PROJECT["functions"]
    # the setpoint is required
    assert _build_platform_suggestion(TEST_PROJECT, functions["F-5"]) is None
    # a custom function has no entity
    assert _build_platform_suggestion(TEST_PROJECT, functions["F-6"]) is None
    assert _build_platform_suggestion(TEST_PROJECT, functions["F-7"]) is None
    # a configuration the platform schema rejects
    function = _function("Light", "FT-1", "P-2", ("1/0/1", "InfoOnOff"))
    assert _build_platform_suggestion(TEST_PROJECT, function) is None


async def test_ws_get_entity_suggestions(
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    get_entity_suggestions: KnxSuggestionGetter,
    hass_storage: dict[str, Any],
) -> None:
    """Test the knx/get_entity_suggestions command with functions."""
    hass_storage[KNX_PROJECT_STORAGE_KEY] = {"version": 1, "data": TEST_PROJECT}
    await knx.setup_integration()
    entity = await create_ui_entity(Platform.SWITCH, {"ga_switch": {"write": "4/0/1"}})

    result = await get_entity_suggestions()
    assert result["providers"]["function"] == {"state": "ok", "functions_found": 7}
    suggestions = {
        suggestion["id"]: suggestion
        for suggestion in result["suggestions"]
        if suggestion["source"] == "function"
    }
    assert sorted(suggestions) == [
        "function_F-1",
        "function_F-2",
        "function_F-3",
        "function_F-4",
    ]
    ceiling = suggestions["function_F-1"]
    assert ceiling["suggested_name"] == "Ceiling"
    # grouped by the room the function is in
    assert ceiling["group_id"] == "P-2"
    assert ceiling["group_name"] == "Kitchen"
    assert ceiling["secondary_info"] == "FT-6"
    assert ceiling["platform_options"] == ["light"]
    assert ceiling["metadata"] == {"function_type": "FT-6"}
    assert ceiling["existing_entity_ids"] == []
    assert suggestions["function_F-4"]["existing_entity_ids"] == [entity.entity_id]


async def test_ws_get_entity_suggestions_no_project(
    knx: KNXTestKit,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test suggestions without project data."""
    await knx.setup_integration()
    result = await get_entity_suggestions()
    assert result["providers"]["function"] == {"state": "no_project"}


async def test_ws_get_entity_suggestions_no_functions(
    knx: KNXTestKit,
    get_entity_suggestions: KnxSuggestionGetter,
    hass_storage: dict[str, Any],
) -> None:
    """Test suggestions for a project without functions."""
    project = {key: value for key, value in TEST_PROJECT.items() if key != "functions"}
    hass_storage[KNX_PROJECT_STORAGE_KEY] = {"version": 1, "data": project}
    await knx.setup_integration()
    result = await get_entity_suggestions()
    assert result["providers"]["function"] == {"state": "no_functions"}
    assert all(s["source"] != "function" for s in result["suggestions"])
