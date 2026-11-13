"""Test KNX entity suggestions generated from building functions."""

from typing import Any

from homeassistant.components.knx.project import STORAGE_KEY as KNX_PROJECT_STORAGE_KEY
from homeassistant.components.knx.storage.entity_suggestions.functions import (
    FUNCTION_ENTITIES,
    FUNCTION_POINTS,
    _build_platform_suggestion,
    _function_roles,
    _role_targets,
)
from homeassistant.const import Platform

from . import KnxEntityGenerator, KnxSuggestionGetter
from .conftest import KNXTestKit

DPT_SWITCH = {"main": 1, "sub": 1}
DPT_STATE = {"main": 1, "sub": 11}
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
        "3/0/6": _group_address("3/0/6", DPT_TEMPERATURE),
        "4/0/1": _group_address("4/0/1", DPT_SWITCH),
        "4/0/2": _group_address("4/0/2", DPT_STATE),
        "5/0/1": _group_address("5/0/1", DPT_COUNTER),
        "5/0/2": _group_address("5/0/2", DPT_PERCENT_ANY),
        "6/0/1": _group_address("6/0/1", None),
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
        # roles from the DPTs - the second 5.001 point makes the position ambiguous
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


def _com_object(
    address: str, write: bool, communication: bool = True, read: bool | None = None
) -> dict[str, Any]:
    return {
        "group_address_links": [address],
        "flags": {
            "read": not write if read is None else read,
            "write": write,
            "communication": communication,
            "transmit": not write,
            "update": False,
            "read_on_init": False,
        },
    }


def test_role_targets() -> None:
    """Test every role of an entity resolves to a config key of its platform."""
    for function_type, entity in FUNCTION_ENTITIES.items():
        points = {role for role, _dpt in FUNCTION_POINTS[function_type]}
        targets = _role_targets(function_type)
        assert set(targets) == (set(entity.dpas) | set(entity.roles)) & points
        assert set(entity.required) <= set(targets)
    # a switching valve is only a point of the switching heating
    assert "ValveSwitch" in _role_targets("FT-8")
    assert "ValveSwitch" not in _role_targets("FT-9")


def test_stored_and_inferred_roles() -> None:
    """Test a stored role is kept and a role is inferred from an unambiguous DPT."""
    function = _function(
        "Light", "FT-6", "P-2", ("1/0/3", ""), ("1/0/1", ""), ("1/0/2", "InfoOnOff")
    )
    roles = _function_roles(TEST_PROJECT, function)
    # 1.001 only fits the free switching point; 5.001 fits two brightness points
    assert roles.addresses == {"InfoOnOff": "1/0/2", "SwitchOnOff": "1/0/1"}
    assert roles.inferred == {"SwitchOnOff"}
    # a role of another type on an address without DPT: nothing is inferred
    function = _function("Socket", "FT-10", "P-2", ("6/0/1", "MoveUpDown"))
    assert _function_roles(TEST_PROJECT, function).addresses == {}
    # a stored role is the user's statement, also without a DPT
    function = _function("Socket", "FT-10", "P-2", ("6/0/1", "SwitchOnOff"))
    roles = _function_roles(TEST_PROJECT, function)
    assert roles.addresses == {"SwitchOnOff": "6/0/1"}
    assert roles.inferred == set()


def test_ambiguous_dpts_are_not_inferred() -> None:
    """Test a role-less address whose DPT fits several free points stays unmatched."""
    # switching and status are both 1.001
    function = _function("Light", "FT-1", "P-2", ("1/0/1", ""), ("1/0/2", ""))
    assert _function_roles(TEST_PROJECT, function).addresses == {}
    assert _build_platform_suggestion(TEST_PROJECT, function) is None
    # room temperature and setpoint are both 9.001
    function = _function(
        "Radiator",
        "FT-9",
        "P-3",
        ("3/0/1", ""),
        ("3/0/2", ""),
        ("3/0/3", ""),
        ("3/0/4", ""),
    )
    roles = _function_roles(TEST_PROJECT, function)
    assert roles.addresses == {"ValvePosition": "3/0/3", "HVACMode": "3/0/4"}
    assert _build_platform_suggestion(TEST_PROJECT, function) is None
    # blinds and slat position are both 5.001
    function = _function(
        "Blind", "FT-7", "P-3", ("2/0/1", ""), ("2/0/3", ""), ("1/0/3", "")
    )
    assert _function_roles(TEST_PROJECT, function).addresses == {"MoveUpDown": "2/0/1"}
    platform, suggestion, roles_used = _build_platform_suggestion(
        TEST_PROJECT, function
    )
    assert platform is Platform.COVER
    assert suggestion["knx"] == {"ga_up_down": {"write": "2/0/1", "passive": []}}
    assert suggestion["unmatched"] == ["1/0/3", "2/0/3"]
    assert roles_used == {"MoveUpDown": "inferred"}
    # two role-less addresses fitting the one free point
    function = _function(
        "Light", "FT-1", "P-2", ("1/0/2", "InfoOnOff"), ("1/0/1", ""), ("4/0/1", "")
    )
    assert _function_roles(TEST_PROJECT, function).addresses == {"InfoOnOff": "1/0/2"}


def test_status_address_of_a_push_button_feedback() -> None:
    """Test a status address a push button's feedback object receives."""
    project = {
        **TEST_PROJECT,
        "communication_objects": {
            # the actuator switches on 1/0/1 and sends its status on 1/0/2
            "O-1": _com_object("1/0/1", write=True),
            "O-2": _com_object("1/0/2", write=False),
            # the feedback object of a push button receives the status
            "O-3": _com_object("1/0/2", write=True),
        },
    }
    function = _function("Light", "FT-1", "P-2", ("1/0/2", ""), ("1/0/1", ""))
    assert _function_roles(project, function).addresses == {}
    assert _build_platform_suggestion(project, function) is None
    # with the switching address stored, the status address is the free point
    function = _function(
        "Light", "FT-1", "P-2", ("1/0/2", ""), ("1/0/1", "SwitchOnOff")
    )
    roles = _function_roles(project, function)
    assert roles.addresses == {"SwitchOnOff": "1/0/1", "InfoOnOff": "1/0/2"}
    assert roles.inferred == {"InfoOnOff"}


def test_second_address_of_a_stored_role() -> None:
    """Test a second address stored with a taken role is not given another role."""
    function = _function(
        "Light", "FT-1", "P-2", ("1/0/2", "InfoOnOff"), ("1/0/1", "InfoOnOff")
    )
    # a second status address doesn't become the switching command
    assert _function_roles(TEST_PROJECT, function).addresses == {"InfoOnOff": "1/0/2"}
    assert _build_platform_suggestion(TEST_PROJECT, function) is None


def test_stored_roles_fit_the_selector() -> None:
    """Test a stored role is checked against what its config key accepts."""
    # a status of DPT 1.011 is accepted by the switch address of a light
    function = _function(
        "Light", "FT-1", "P-2", ("1/0/1", "SwitchOnOff"), ("4/0/2", "InfoOnOff")
    )
    _platform, suggestion, _roles = _build_platform_suggestion(TEST_PROJECT, function)
    assert suggestion["knx"] == {
        "ga_switch": {"write": "1/0/1", "state": "4/0/2", "passive": []},
    }
    # a temperature is no switching address
    function = _function(
        "Socket", "FT-10", "P-2", ("3/0/1", "SwitchOnOff"), ("1/0/2", "InfoOnOff")
    )
    assert _function_roles(TEST_PROJECT, function).addresses == {"InfoOnOff": "1/0/2"}
    # the brightness is a percentage (5.001): no count (5.010), no bare DPT 5
    function = _function("Light", "FT-6", "P-2", ("5/0/1", "DimmingValue"))
    assert _function_roles(TEST_PROJECT, function).addresses == {}
    function = _function("Light", "FT-6", "P-2", ("5/0/2", "DimmingValue"))
    assert _function_roles(TEST_PROJECT, function).addresses == {}
    function = _function("Light", "FT-6", "P-2", ("1/0/3", "DimmingValue"))
    assert _function_roles(TEST_PROJECT, function).addresses == {
        "DimmingValue": "1/0/3"
    }
    # inferred roles need the DPT of the function point
    function = _function("Light", "FT-6", "P-2", ("5/0/1", ""), ("1/0/2", "InfoOnOff"))
    assert _function_roles(TEST_PROJECT, function).addresses == {"InfoOnOff": "1/0/2"}


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
    # stored as the command, but nothing receives it
    function = _function("Light", "FT-1", "P-2", ("1/0/2", "SwitchOnOff"))
    assert _function_roles(project, function).addresses == {}
    assert _build_platform_suggestion(project, function) is None
    # without linked objects in the project, the receivers are unknown
    function = _function("Socket", "FT-10", "P-2", ("4/0/1", "SwitchOnOff"))
    assert _function_roles(project, function).addresses == {"SwitchOnOff": "4/0/1"}
    # an object without the communication flag takes no part on the bus
    project["communication_objects"]["O-3"] = _com_object(
        "4/0/1", write=True, communication=False
    )
    assert _function_roles(project, function).addresses == {}


def test_read_back_needs_an_answering_object() -> None:
    """Test a command address is only read back when a linked object answers."""
    project = {
        **TEST_PROJECT,
        "communication_objects": {
            # the controller takes the setpoint, but doesn't answer reads of it
            "O-1": _com_object("3/0/2", write=True, read=False),
            "O-2": _com_object("3/0/4", write=True, read=True),
        },
    }
    _platform, suggestion, _roles = _build_platform_suggestion(
        project, TEST_PROJECT["functions"]["F-3"]
    )
    knx = suggestion["knx"]
    assert knx["target_temperature"]["ga_temperature_target"] == {
        "write": "3/0/2",
        "passive": [],
    }
    assert knx["ga_operation_mode"] == {
        "write": "3/0/4",
        "state": "3/0/4",
        "passive": [],
    }


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
    platform, suggestion, _roles = _build_platform_suggestion(TEST_PROJECT, function)
    assert platform is Platform.LIGHT
    assert suggestion["knx"] == {
        "ga_switch": {"write": "1/0/1", "state": "1/0/2", "passive": []},
    }
    assert suggestion["unmatched"] == ["1/0/4"]


def test_dimmable_light() -> None:
    """Test a dimmable light with switching and brightness."""
    platform, suggestion, roles = _build_platform_suggestion(
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
    assert set(roles.values()) == {"stored"}


def test_deprecated_dimmable_light() -> None:
    """Test the value of a deprecated dimmable light is its brightness command."""
    function = _function(
        "Light",
        "FT-2",
        "P-2",
        ("1/0/1", "SwitchOnOff"),
        ("1/0/2", "InfoOnOff"),
        ("1/0/3", "InfoDimmingValue"),
    )
    _platform, suggestion, _roles = _build_platform_suggestion(TEST_PROJECT, function)
    assert suggestion["knx"]["ga_brightness"] == {"write": "1/0/3", "passive": []}


def test_sun_protection() -> None:
    """Test a cover from roles inferred from their DPT."""
    platform, suggestion, roles = _build_platform_suggestion(
        TEST_PROJECT, TEST_PROJECT["functions"]["F-2"]
    )
    assert platform is Platform.COVER
    assert suggestion["knx"]["ga_up_down"]["write"] == "2/0/1"
    assert suggestion["knx"]["ga_step"]["write"] == "2/0/2"
    # blinds or slat position: not guessed
    assert "ga_position_state" not in suggestion["knx"]
    assert suggestion["unmatched"] == ["2/0/3"]
    assert roles == {"MoveUpDown": "inferred", "StopStepUpDown": "inferred"}
    # stored, the position is used
    function = _function(
        "Blind",
        "FT-7",
        "P-3",
        ("2/0/1", "MoveUpDown"),
        ("2/0/3", "CurrentAbsolutePositionBlindsPercentage"),
    )
    _platform, suggestion, _roles = _build_platform_suggestion(TEST_PROJECT, function)
    assert suggestion["knx"]["ga_position_state"]["state"] == "2/0/3"


def test_heating() -> None:
    """Test a climate entity with its setpoint written and read on one address."""
    platform, suggestion, _roles = _build_platform_suggestion(
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
    _platform, suggestion, _roles = _build_platform_suggestion(TEST_PROJECT, function)
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
    assert result["providers"]["function"] == {
        "state": "ok",
        "function_types_found": [
            "FT-0",
            "FT-1",
            "FT-10",
            "FT-6",
            "FT-7",
            "FT-8",
            "FT-9",
        ],
    }
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
    assert ceiling["metadata"] == {
        "function_type": "FT-6",
        "roles": {
            "SwitchOnOff": "stored",
            "InfoOnOff": "stored",
            "DimmingValue": "stored",
            "InfoDimmingValue": "stored",
        },
    }
    assert ceiling["existing_entity_ids"] == []
    assert suggestions["function_F-2"]["metadata"]["roles"] == {
        "MoveUpDown": "inferred",
        "StopStepUpDown": "inferred",
    }
    assert suggestions["function_F-4"]["existing_entity_ids"] == [entity.entity_id]


async def test_ws_get_entity_suggestions_no_project(
    knx: KNXTestKit,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test suggestions without project data."""
    await knx.setup_integration()
    result = await get_entity_suggestions()
    assert result["providers"]["function"] == {"state": "no_project"}


async def test_ws_get_entity_suggestions_outdated_parser(
    knx: KNXTestKit,
    get_entity_suggestions: KnxSuggestionGetter,
    hass_storage: dict[str, Any],
) -> None:
    """Test suggestions for project data of a parser without functions."""
    project = {
        **{key: value for key, value in TEST_PROJECT.items() if key != "functions"},
        "info": {**TEST_PROJECT["info"], "xknxproject_version": "3.2.0"},
    }
    hass_storage[KNX_PROJECT_STORAGE_KEY] = {"version": 1, "data": project}
    await knx.setup_integration()
    result = await get_entity_suggestions()
    assert result["providers"]["function"] == {
        "state": "outdated_parser",
        "parser_version": "3.2.0",
    }


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
