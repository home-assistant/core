"""Test KNX entity suggestions from existing entity configurations."""

from typing import Any

import pytest

from homeassistant.components.knx.project import STORAGE_KEY as KNX_PROJECT_STORAGE_KEY
from homeassistant.components.knx.storage.entity_suggestions.existing_config import (
    _apply,
    _source_addresses,
)
from homeassistant.components.knx.storage.entity_suggestions.ga_mapping import (
    ChannelMapping,
    ChannelRef,
    MappedAddress,
)
from homeassistant.const import Platform

from . import KnxEntityGenerator, KnxSuggestionGetter
from .conftest import KNXTestKit

APP_COVER = "M-0001_A-COVER"
APP_SWITCH = "M-0001_A-SWITCH"
APP_BUTTON = "M-0002_A-BUTTON"


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


def _device(name: str, application: str, channels: list[str] | None = None) -> dict:
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

_ALL_OBJECTS = _COVER_OBJECTS + _SWITCH_OBJECTS + _BUTTON_OBJECTS


def _project() -> dict[str, Any]:
    """Build a project out of the objects above."""
    communication_objects = {
        f"{com_object['device_address']}/O-{index}": com_object
        for index, com_object in enumerate(_ALL_OBJECTS)
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
        "devices": {
            "1.0.1": _device("Cover actuator", APP_COVER, ["CH-1", "CH-2"]),
            "1.0.2": _device("Cover actuator 2", APP_COVER, ["CH-1", "CH-2"]),
            "1.0.10": _device("Switch actuator", APP_SWITCH),
            "1.0.11": _device("Switch actuator 2", APP_SWITCH),
            "1.0.12": _device("Switch actuator 3", APP_SWITCH),
            "1.1.1": _device("Push button", APP_BUTTON, ["CH-1", "CH-2"]),
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
