"""Test KNX entity suggestions from existing entity configurations."""

from typing import Any

import pytest

from homeassistant.components.knx.project import STORAGE_KEY as KNX_PROJECT_STORAGE_KEY
from homeassistant.components.knx.storage.entity_suggestions.existing_config import (
    _apply,
    _matched_group_addresses,
    _source_addresses,
)
from homeassistant.components.knx.storage.entity_suggestions.ga_mapping import (
    ChannelMapping,
    ChannelRef,
    MappedAddress,
    SourceAddress,
    build_project_index,
    derive_channel_mappings,
)
from homeassistant.const import Platform

from . import KnxEntityGenerator, KnxSuggestionGetter
from .conftest import KNXTestKit

APP_COVER = "M-0001_A-COVER"
APP_SWITCH = "M-0001_A-SWITCH"
APP_BUTTON = "M-0002_A-BUTTON"
APP_DALI = "M-0003_A-DALI"


def _flags(write: bool = False, transmit: bool = False, read: bool = False) -> dict:
    return {
        "write": write,
        "transmit": transmit,
        "read": read,
        "communication": True,
        "update": False,
        "read_on_init": False,
    }


def _com_object(
    number: int,
    device: str,
    function_text: str,
    ga_links: list[str],
    *,
    channel: str | None = None,
    text: str = "",
    dpts: list[dict] | None = None,
    module_def: dict | None = None,
    **flag_values: bool,
) -> dict:
    return {
        "name": f"KO {number}",
        "number": number,
        "text": text,
        "function_text": function_text,
        "description": "",
        "device_address": device,
        "device_application": None,
        "module_def": module_def,
        "channel": channel,
        "dpts": dpts or [{"main": 1, "sub": None}],
        "object_size": "1 Bit",
        "group_address_links": ga_links,
        "flags": _flags(**flag_values),
        "dpas": None,
    }


def _device(
    name: str,
    application: str,
    channels: list[str] | None = None,
    group_object_tree: list[dict] | None = None,
) -> dict:
    return {
        "name": name,
        "hardware_name": name,
        "description": "",
        "manufacturer_name": "Test",
        "individual_address": "",
        "application": application,
        "project_uid": None,
        "communication_object_ids": [],
        "channels": {
            channel: {
                "identifier": channel,
                "name": f"Output {channel}",
                "communication_object_ids": [],
                "functional_blocks": None,
            }
            for channel in channels or []
        },
        "group_object_tree": group_object_tree or [],
    }


def _node(
    node_type: str, identifier: str, name: str, numbers: list[int], device: str
) -> dict:
    return {
        "type": node_type,
        "identifier": identifier,
        "name": name,
        "communication_object_ids": [f"{device}/O-{number}" for number in numbers],
        "nodes": [],
    }


DPT_PERCENT = [{"main": 5, "sub": 1}]

# a cover actuator with two channels, and an identical second one
_COVER_OBJECTS = [
    # 1.0.1 channel CH-1 - the channel the template is built on
    _com_object(1, "1.0.1", "Move", ["1/0/1"], channel="CH-1", write=True),
    _com_object(2, "1.0.1", "Stop", ["1/0/2"], channel="CH-1", write=True),
    _com_object(
        3, "1.0.1", "Position", ["1/0/3"], channel="CH-1", dpts=DPT_PERCENT, write=True
    ),
    _com_object(
        4,
        "1.0.1",
        "Position status",
        ["1/0/4"],
        channel="CH-1",
        dpts=DPT_PERCENT,
        transmit=True,
        read=True,
    ),
    # 1.0.1 channel CH-2 - matched by function text
    _com_object(11, "1.0.1", "Move", ["1/1/1"], channel="CH-2", write=True),
    _com_object(12, "1.0.1", "Stop", ["1/1/2"], channel="CH-2", write=True),
    _com_object(
        13, "1.0.1", "Position", ["1/1/3"], channel="CH-2", dpts=DPT_PERCENT, write=True
    ),
    _com_object(
        14,
        "1.0.1",
        "Position status",
        ["1/1/4"],
        channel="CH-2",
        dpts=DPT_PERCENT,
        transmit=True,
        read=True,
    ),
    # 1.0.2 - same application, so its objects are numbered the same
    _com_object(1, "1.0.2", "Move", ["2/0/1"], channel="CH-1", write=True),
    _com_object(2, "1.0.2", "Stop", ["2/0/2"], channel="CH-1", write=True),
    _com_object(
        3, "1.0.2", "Position", ["2/0/3"], channel="CH-1", dpts=DPT_PERCENT, write=True
    ),
    _com_object(
        4,
        "1.0.2",
        "Position status",
        ["2/0/4"],
        channel="CH-1",
        dpts=DPT_PERCENT,
        transmit=True,
        read=True,
    ),
    # 1.0.2 channel CH-2 offers no position - that key is dropped
    _com_object(11, "1.0.2", "Move", ["2/1/1"], channel="CH-2", write=True),
    _com_object(12, "1.0.2", "Stop", ["2/1/2"], channel="CH-2", write=True),
]

# a switch actuator whose application has no channels - its objects are only
# told apart by their text - and an identical second one
_SWITCH_OBJECTS = [
    _com_object(20, "1.0.10", "Switch", ["3/0/1"], text="Channel A", write=True),
    _com_object(
        21, "1.0.10", "Status", ["3/0/2"], text="Channel A", transmit=True, read=True
    ),
    _com_object(22, "1.0.10", "Switch", ["3/1/1"], text="Channel B", write=True),
    _com_object(
        23, "1.0.10", "Status", ["3/1/2"], text="Channel B", transmit=True, read=True
    ),
    _com_object(20, "1.0.11", "Switch", ["4/0/1"], text="Channel A", write=True),
    _com_object(
        21, "1.0.11", "Status", ["4/0/2"], text="Channel A", transmit=True, read=True
    ),
    # this channel only reports, it cannot be switched
    _com_object(
        23, "1.0.11", "Status", ["4/1/2"], text="Channel B", transmit=True, read=True
    ),
    # parameters of this channel make its object set a value instead of switching
    _com_object(
        20,
        "1.0.12",
        "Value",
        ["4/2/1"],
        text="Channel A",
        dpts=DPT_PERCENT,
        write=True,
    ),
    _com_object(
        21, "1.0.12", "Status", ["4/2/2"], text="Channel A", transmit=True, read=True
    ),
    # this channel is switched in parallel with "Channel A" of the first device
    _com_object(22, "1.0.12", "Switch", ["3/0/1"], text="Channel B", write=True),
]

# a push button linked to the very same addresses - a single object of it both
# sends the command and receives the status
_BUTTON_OBJECTS = [
    _com_object(
        1,
        "1.1.1",
        "Rocker",
        ["3/0/1", "3/0/2"],
        channel="CH-1",
        write=True,
        transmit=True,
    ),
    _com_object(
        2,
        "1.1.1",
        "Rocker",
        ["3/9/9"],
        channel="CH-2",
        write=True,
        transmit=True,
    ),
]

# a lighting gateway whose channels offer the brightness and the white colour
# component with objects of the same function text - only the folder they are
# placed in tells them apart
_GATEWAY_OBJECTS = [
    obj
    for channel, base, addresses in (("CH-1", 30, "5/0"), ("CH-2", 40, "5/1"))
    for obj in (
        _com_object(
            base, "1.0.20", "Switch", [f"{addresses}/1"], channel=channel, write=True
        ),
        _com_object(
            base + 1,
            "1.0.20",
            "Dim absolute",
            [f"{addresses}/2"],
            channel=channel,
            dpts=DPT_PERCENT,
            write=True,
        ),
        _com_object(
            base + 2,
            "1.0.20",
            "Status dim value",
            [f"{addresses}/3"],
            channel=channel,
            dpts=DPT_PERCENT,
            transmit=True,
            read=True,
        ),
        _com_object(
            base + 3,
            "1.0.20",
            "Dim absolute",
            [f"{addresses}/4"],
            channel=channel,
            dpts=DPT_PERCENT,
            write=True,
        ),
        _com_object(
            base + 4,
            "1.0.20",
            "Status dim value",
            [f"{addresses}/5"],
            channel=channel,
            dpts=DPT_PERCENT,
            transmit=True,
            read=True,
        ),
    )
]
_GATEWAY_TREE = [
    _node("Channel", channel, f"Group {channel}", [], "1.0.20")
    | {
        "nodes": [
            _node(
                "Folder",
                f"PB-{base}",
                "Behaviour",
                [base, base + 1, base + 2],
                "1.0.20",
            ),
            _node(
                "Folder",
                f"PB-{base + 3}",
                "Colour control",
                [base + 3, base + 4],
                "1.0.20",
            ),
        ]
    }
    for channel, base in (("CH-1", 30), ("CH-2", 40))
]

_ALL_OBJECTS = _COVER_OBJECTS + _SWITCH_OBJECTS + _BUTTON_OBJECTS + _GATEWAY_OBJECTS


def _project(
    objects: list[dict] | None = None, devices: dict[str, dict] | None = None
) -> dict[str, Any]:
    """Build a project - out of the objects above unless others are given."""
    communication_objects = {
        f"{com_object['device_address']}/O-{com_object['number']}": com_object
        for com_object in (_ALL_OBJECTS if objects is None else objects)
    }
    group_addresses: dict[str, Any] = {}
    for com_object_id, com_object in communication_objects.items():
        for address in com_object["group_address_links"]:
            group_address = group_addresses.setdefault(
                address,
                {
                    "name": f"GA {address}",
                    "identifier": address,
                    "raw_address": 0,
                    "address": address,
                    "project_uid": None,
                    "dpt": None,
                    "data_secure": False,
                    "communication_object_ids": [],
                    "description": "",
                    "comment": "",
                },
            )
            group_address["communication_object_ids"].append(com_object_id)
    return {
        "info": {
            "xknxproject_version": "3.10.0",
            "group_address_style": "ThreeLevel",
        },
        "group_addresses": group_addresses,
        "devices": devices
        or {
            "1.0.1": _device("Cover actuator", APP_COVER, ["CH-1", "CH-2"]),
            "1.0.2": _device("Cover actuator 2", APP_COVER, ["CH-1", "CH-2"]),
            "1.0.10": _device("Switch actuator", APP_SWITCH),
            "1.0.11": _device("Switch actuator 2", APP_SWITCH),
            "1.0.12": _device("Switch actuator 3", APP_SWITCH),
            "1.1.1": _device("Push button", APP_BUTTON, ["CH-1", "CH-2"]),
            "1.0.20": _device(
                "Lighting gateway", APP_DALI, ["CH-1", "CH-2"], _GATEWAY_TREE
            ),
        },
        "communication_objects": communication_objects,
    }


COVER_CONFIG = {
    "ga_up_down": {"write": "1/0/1"},
    "ga_stop": {"write": "1/0/2"},
    "ga_position_set": {"write": "1/0/3"},
    "ga_position_state": {"state": "1/0/4"},
    "travelling_time_up": 13,
    "travelling_time_down": 13,
}
SWITCH_CONFIG = {
    "ga_switch": {"write": "3/0/1", "state": "3/0/2"},
    "invert": True,
    "sync_state": "expire 60",
}


@pytest.fixture
def load_project(hass_storage: dict[str, Any]) -> None:
    """Store the test project."""
    hass_storage[KNX_PROJECT_STORAGE_KEY] = {"version": 1, "data": _project()}


def _by_id(result: dict[str, Any]) -> dict[str, Any]:
    return {suggestion["id"]: suggestion for suggestion in result["suggestions"]}


@pytest.mark.usefixtures("load_project")
async def test_suggestions_for_other_channels(
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test a configuration is offered for the channels wired like it."""
    await knx.setup_integration()
    entity = await create_ui_entity(Platform.COVER, COVER_CONFIG)
    await knx.assert_read("1/0/4", (0,))

    result = await get_entity_suggestions()
    assert result["providers"]["cfg"] == {"state": "ok"}
    by_id = _by_id(result)
    assert sorted(by_id) == [
        "cfg_1.0.1_CH-2_cover",
        "cfg_1.0.2_CH-1_cover",
        "cfg_1.0.2_CH-2_cover",
    ]

    # another channel of the same device - matched by what its objects do
    channel_2 = by_id["cfg_1.0.1_CH-2_cover"]
    assert channel_2["suggestions"]["cover"]["knx"] == {
        "ga_up_down": {"write": "1/1/1", "passive": []},
        "ga_stop": {"write": "1/1/2", "passive": []},
        "ga_position_set": {"write": "1/1/3", "passive": []},
        "ga_position_state": {"state": "1/1/4", "passive": []},
        # everything besides the addresses is kept
        "travelling_time_up": 13,
        "travelling_time_down": 13,
        "invert_updown": False,
        "invert_position": False,
        "invert_angle": False,
        "sync_state": True,
    }
    assert channel_2["suggestions"]["cover"]["matched_group_addresses"] == [
        {"address": "1/1/1", "name": "GA 1/1/1"},
        {"address": "1/1/2", "name": "GA 1/1/2"},
        {"address": "1/1/3", "name": "GA 1/1/3"},
        {"address": "1/1/4", "name": "GA 1/1/4"},
    ]
    assert channel_2["source"] == "cfg"
    assert channel_2["platform_options"] == ["cover"]
    assert channel_2["suggested_name"] == "Cover actuator Output CH-2"
    assert channel_2["existing_entity_ids"] == []

    # an identically programmed device numbers its objects the same way
    sibling = by_id["cfg_1.0.2_CH-1_cover"]
    assert sibling["suggestions"]["cover"]["knx"]["ga_up_down"] == {
        "write": "2/0/1",
        "passive": [],
    }
    assert sibling["group_id"] == "1.0.2"
    assert sibling["group_name"] == "Cover actuator 2"
    assert sibling["secondary_info"] == "Output CH-1"
    assert sibling["metadata"] == {"template_entity_id": entity.entity_id}

    # a channel that doesn't offer one of the functions loses that key
    partial = by_id["cfg_1.0.2_CH-2_cover"]["suggestions"]["cover"]
    assert "ga_position_set" not in partial["knx"]
    assert "ga_position_state" not in partial["knx"]
    assert partial["unmatched"] == [
        "ga_position_set.write",
        "ga_position_state.state",
    ]


@pytest.mark.usefixtures("load_project")
@pytest.mark.parametrize(
    "ga_switch",
    [
        {"write": "3/0/1", "state": "3/0/2"},
        # addresses are stored as entered - eg. as raw address
        {"write": 6145, "state": 6146},
    ],
)
async def test_suggestions_for_devices_without_channels(
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    get_entity_suggestions: KnxSuggestionGetter,
    ga_switch: dict[str, Any],
) -> None:
    """Test outputs of an application without channels are covered."""
    await knx.setup_integration()
    await create_ui_entity(Platform.SWITCH, SWITCH_CONFIG | {"ga_switch": ga_switch})
    await knx.assert_read("3/0/2", 0)

    result = await get_entity_suggestions()
    by_id = _by_id(result)
    assert sorted(by_id) == [
        "cfg_1.0.10_Channel B_switch",
        "cfg_1.0.11_Channel A_switch",
    ]

    assert by_id["cfg_1.0.10_Channel B_switch"]["suggestions"]["switch"]["knx"] == {
        "ga_switch": {"write": "3/1/1", "state": "3/1/2", "passive": []},
        "invert": True,
        "respond_to_read": False,
        "sync_state": "expire 60",
    }
    # such objects are named after the output, so the address name is used
    assert by_id["cfg_1.0.10_Channel B_switch"]["suggested_name"] == "GA 3/1/1"
    assert by_id["cfg_1.0.11_Channel A_switch"]["suggestions"]["switch"]["knx"][
        "ga_switch"
    ] == {"write": "4/0/1", "state": "4/0/2", "passive": []}

    # channels that can not be switched like the configured one are not offered:
    # one only reports its state, the object of another one sets a value instead
    assert "cfg_1.0.11_Channel B_switch" not in by_id
    assert "cfg_1.0.12_Channel A_switch" not in by_id
    # a channel using the very same address would only repeat the entity
    assert "cfg_1.0.12_Channel B_switch" not in by_id
    # the push button linked to the same addresses is never a source or target
    assert all(
        suggestion["group_id"] != "1.1.1" for suggestion in result["suggestions"]
    )


@pytest.mark.usefixtures("load_project")
async def test_most_complete_configuration_is_suggested(
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test the configuration covering most of a channel is the one suggested."""
    await knx.setup_integration()
    basic = await create_ui_entity(
        Platform.COVER,
        {"ga_up_down": {"write": "2/1/1"}, "ga_stop": {"write": "2/1/2"}},
        {"name": "Basic"},
    )
    full = await create_ui_entity(Platform.COVER, COVER_CONFIG, {"name": "Full"})
    await knx.assert_read("1/0/4", (0,))

    by_id = _by_id(await get_entity_suggestions())
    # both configurations suggest the channels of the other, each offered once
    assert sorted(by_id) == [
        "cfg_1.0.1_CH-1_cover",
        "cfg_1.0.1_CH-2_cover",
        "cfg_1.0.2_CH-1_cover",
        "cfg_1.0.2_CH-2_cover",
    ]
    # the first configuration could be applied too, but it would leave the
    # position of that channel unused
    for suggestion_id in ("cfg_1.0.1_CH-2_cover", "cfg_1.0.2_CH-1_cover"):
        suggestion = by_id[suggestion_id]
        assert suggestion["metadata"] == {"template_entity_id": full.entity_id}
        assert "ga_position_set" in suggestion["suggestions"]["cover"]["knx"]
        assert suggestion["existing_entity_ids"] == []
    # the channels that already have an entity are reported as such
    assert by_id["cfg_1.0.1_CH-1_cover"]["existing_entity_ids"] == [full.entity_id]
    assert by_id["cfg_1.0.2_CH-2_cover"]["existing_entity_ids"] == [basic.entity_id]

    unconfigured = _by_id(await get_entity_suggestions(include_configured=False))
    assert sorted(unconfigured) == ["cfg_1.0.1_CH-2_cover", "cfg_1.0.2_CH-1_cover"]


@pytest.mark.parametrize(
    ("with_tree", "brightness"),
    [
        (True, {"write": "5/1/2", "state": "5/1/3", "passive": []}),
        # project data stored by an older parser has no group object tree - an
        # ambiguous function is left out rather than guessed
        (False, None),
    ],
)
async def test_functions_told_apart_by_folders(
    hass_storage: dict[str, Any],
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    get_entity_suggestions: KnxSuggestionGetter,
    with_tree: bool,
    brightness: dict[str, Any] | None,
) -> None:
    """Test objects of the same function are matched by the folder they are in."""
    project = _project()
    if not with_tree:
        for device in project["devices"].values():
            del device["group_object_tree"]
    hass_storage[KNX_PROJECT_STORAGE_KEY] = {"version": 1, "data": project}
    await knx.setup_integration()
    await create_ui_entity(
        Platform.LIGHT,
        {
            "ga_switch": {"write": "5/0/1"},
            "ga_brightness": {"write": "5/0/2", "state": "5/0/3"},
        },
    )
    await knx.assert_read("5/0/3", (0,))

    by_id = _by_id(await get_entity_suggestions())
    assert list(by_id) == ["cfg_1.0.20_CH-2_light"]
    suggestion = by_id["cfg_1.0.20_CH-2_light"]["suggestions"]["light"]
    assert suggestion["knx"]["ga_switch"] == {
        "write": "5/1/1",
        "state": None,
        "passive": [],
    }
    assert suggestion["knx"].get("ga_brightness") == brightness
    assert suggestion["unmatched"] == (
        [] if brightness else ["ga_brightness.state", "ga_brightness.write"]
    )


def _folder_project(
    objects: list[dict], tree: list[dict], channels: list[str] | None = None
) -> dict[str, Any]:
    """Build a project of a single device with a group object tree."""
    return _project(
        objects,
        {"1.0.30": _device("Gateway", APP_DALI, channels or ["CH-1", "CH-2"], tree)},
    )


def _dim_object(number: int, channel: str, address: str, **kwargs: Any) -> dict:
    return _com_object(
        number,
        "1.0.30",
        kwargs.pop("function_text", "Dim absolute"),
        [address],
        channel=channel,
        dpts=DPT_PERCENT,
        write=True,
        **kwargs,
    )


def _folder(name: str, numbers: list[int], nodes: list[dict] | None = None) -> dict:
    return _node("Folder", f"PB-{name}-{numbers}", name, numbers, "1.0.30") | {
        "nodes": nodes or []
    }


def _channel(identifier: str, nodes: list[dict]) -> dict:
    return _node("Channel", identifier, identifier, [], "1.0.30") | {"nodes": nodes}


def test_lone_match_in_other_folder_is_not_used() -> None:
    """Test an object of the same function text in another folder is no match.

    Only linked objects are part of project data, so the brightness object of
    a channel may be missing while its colour object of the same text is not.
    """
    project = _folder_project(
        [
            _dim_object(1, "CH-1", "6/0/1", function_text="Switch"),
            _dim_object(2, "CH-1", "6/0/2"),
            _dim_object(11, "CH-2", "6/1/1", function_text="Switch"),
            _dim_object(13, "CH-2", "6/1/3"),
        ],
        [
            _channel("CH-1", [_folder("Behaviour", [1, 2])]),
            _channel(
                "CH-2", [_folder("Behaviour", [11]), _folder("Colour control", [13])]
            ),
        ],
    )
    mappings = derive_channel_mappings(
        build_project_index(project),
        [
            SourceAddress("switch", "6/0/1", "write"),
            SourceAddress("brightness", "6/0/2", "write"),
        ],
    )
    assert len(mappings) == 1
    assert mappings[0].target == ChannelRef("1.0.30", "CH-2")
    assert mappings[0].addresses == {"switch": MappedAddress("6/1/1")}
    assert mappings[0].unmatched == ["brightness"]


def test_lone_match_without_folder_is_used() -> None:
    """Test folders only rule a match out if both objects are in one."""
    project = _folder_project(
        [_dim_object(2, "CH-1", "6/0/2"), _dim_object(12, "CH-2", "6/1/2")],
        # the object of CH-2 is placed directly in its channel
        [_channel("CH-1", [_folder("Behaviour", [2])])],
    )
    mappings = derive_channel_mappings(
        build_project_index(project),
        [SourceAddress("brightness", "6/0/2", "write")],
    )
    assert [mapping.addresses for mapping in mappings] == [
        {"brightness": MappedAddress("6/1/2")}
    ]


def test_nested_folders_are_compared_as_path() -> None:
    """Test folders of the same name below different folders are told apart."""
    project = _folder_project(
        [
            _dim_object(2, "CH-1", "6/0/2"),
            _dim_object(12, "CH-2", "6/1/2"),
            _dim_object(13, "CH-2", "6/1/3"),
        ],
        [
            _channel("CH-1", [_folder("Colour control", [], [_folder("Dim", [2])])]),
            _channel(
                "CH-2",
                [
                    _folder("Behaviour", [], [_folder("Dim", [12])]),
                    _folder("Colour control", [], [_folder("Dim", [13])]),
                ],
            ),
        ],
    )
    mappings = derive_channel_mappings(
        build_project_index(project),
        [SourceAddress("white", "6/0/2", "write")],
    )
    assert [mapping.addresses for mapping in mappings] == [
        {"white": MappedAddress("6/1/3")}
    ]


def test_module_instances_told_apart_by_folders() -> None:
    """Test objects of the same module definition are matched by their folder."""
    module_def = {"definition": "MD-1", "root_number": 1}
    project = _folder_project(
        [
            _dim_object(2, "CH-1", "6/0/2", module_def=module_def),
            # the function texts differ - only the module identifies these
            _dim_object(
                12, "CH-2", "6/1/2", module_def=module_def, function_text="Dim %"
            ),
            _dim_object(
                13, "CH-2", "6/1/3", module_def=module_def, function_text="Dim %"
            ),
        ],
        [
            _channel("CH-1", [_folder("Behaviour", [2])]),
            _channel(
                "CH-2", [_folder("Colour control", [13]), _folder("Behaviour", [12])]
            ),
        ],
    )
    mappings = derive_channel_mappings(
        build_project_index(project),
        [SourceAddress("brightness", "6/0/2", "write")],
    )
    assert [mapping.addresses for mapping in mappings] == [
        {"brightness": MappedAddress("6/1/2")}
    ]


def test_folder_index() -> None:
    """Test folders are indexed relative to the channel they are in."""
    project = _folder_project(
        [
            _dim_object(1, "CH-1", "6/0/1"),
            _dim_object(2, "CH-1", "6/0/2"),
            _dim_object(3, "CH-1", "6/0/3"),
            _com_object(4, "1.0.30", "Central", ["6/0/4"], write=True),
        ],
        [
            # 99 is not part of the project - eg. data of another parser version
            _folder("General", [4, 99]),
            _folder(
                "Outputs",
                [],
                [
                    _node("Channel", "CH-1", "Group 1", [1], "1.0.30")
                    | {
                        "nodes": [
                            _folder("Behaviour", [2], [_folder("Dim", [3])]),
                        ]
                    }
                ],
            ),
        ],
        ["CH-1"],
    )
    assert build_project_index(project).folders == {
        # a folder that is in no channel
        ("1.0.30", 4): ("General",),
        # folders above a channel are not part of the path;
        # object 1 is placed directly in its channel
        ("1.0.30", 2): ("Behaviour",),
        ("1.0.30", 3): ("Behaviour", "Dim"),
    }


async def test_no_project(
    knx: KNXTestKit,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test the hint reported without project data."""
    await knx.setup_integration()
    result = await get_entity_suggestions()
    assert result["suggestions"] == []
    assert result["providers"]["cfg"] == {"state": "no_project"}


@pytest.mark.usefixtures("load_project")
async def test_no_ui_entities(
    knx: KNXTestKit,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test the hint reported without any configuration to learn from."""
    await knx.setup_integration()
    result = await get_entity_suggestions()
    assert result["suggestions"] == []
    assert result["providers"]["cfg"] == {"state": "no_ui_entities"}


def test_source_addresses() -> None:
    """Test the addressed group addresses are read out of a configuration."""
    addresses = _source_addresses(
        {
            "ga_switch": {"write": "1/2/3", "state": "1/2/4", "passive": ["1/2/9"]},
            "color": {"ga_color": {"write": "1/2/5", "state": None, "passive": []}},
            # not part of a project
            "ga_lock": {"write": "i-lock", "passive": []},
            "invert": True,
        }
    )
    # passive addresses are alternatives of the same function, not a role
    assert [
        (address.reference, address.address, address.slot) for address in addresses
    ] == [
        ("ga_switch.write", "1/2/3", "write"),
        ("ga_switch.state", "1/2/4", "state"),
        ("color.ga_color.write", "1/2/5", "write"),
    ]


def test_apply() -> None:
    """Test only what the mapping mentions is replaced."""
    config = {
        "ga_switch": {"write": "1/2/3", "state": "1/2/4", "passive": ["1/2/9"]},
        "ga_lock": {"write": "0/0/1", "passive": []},
        "color": {"ga_color": {"write": "1/2/5", "passive": []}},
        "invert": True,
    }
    mapping = ChannelMapping(
        target=ChannelRef("1.0.1", "CH-2"),
        device_name="Device",
        channel_name="Output",
        addresses={
            "ga_switch.write": MappedAddress("5/5/1", ["5/5/8"]),
            "ga_switch.state": MappedAddress("5/5/2"),
        },
        unmatched=["color.ga_color.write"],
    )
    assert _apply(config, mapping) == {
        # the passive addresses of the source belong to its channel
        "ga_switch": {"write": "5/5/1", "state": "5/5/2", "passive": ["5/5/8"]},
        # not mentioned by the mapping - a device global object
        "ga_lock": {"write": "0/0/1", "passive": []},
        # the target channel doesn't offer it
        "color": {},
        "invert": True,
    }
    # the configuration the mapping is applied to stays as it is
    assert config["ga_switch"]["write"] == "1/2/3"


def test_matched_group_addresses() -> None:
    """Test addresses shared with the template don't count as used by a channel."""
    template = {
        "ga_switch": {"write": "3/0/1", "state": "3/0/2", "passive": []},
        # a central object all channels of the device share
        "ga_lock": {"write": "3/9/9", "passive": []},
    }
    knx_config = {
        "ga_switch": {"write": "3/1/1", "state": "3/1/2", "passive": ["3/0/1"]},
        "ga_lock": {"write": "3/9/9", "passive": []},
    }
    assert _matched_group_addresses(_project(), knx_config, template) == [
        {"address": "3/1/1", "name": "GA 3/1/1"},
        {"address": "3/1/2", "name": "GA 3/1/2"},
    ]
