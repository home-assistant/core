"""Test the KNX entity suggestion API."""

from typing import Any, override
from unittest.mock import patch

import pytest

from homeassistant.components.knx.project import STORAGE_KEY as KNX_PROJECT_STORAGE_KEY
from homeassistant.components.knx.storage.entity_suggestions.base import (
    SuggestionProvider,
)
from homeassistant.components.knx.storage.entity_suggestions.const import (
    PlatformSuggestion,
    ProviderResult,
    ProviderSuggestion,
    SuggestedGroupAddress,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import KnxEntityGenerator, KnxSuggestionGetter
from .conftest import KNXTestKit

# an entity is created on this address to test duplicate reporting
CONFIGURED_ADDRESS = "1/2/5"


def _suggestion(
    suggestion_id: str,
    platform: Platform,
    address: str,
    group_id: str = "1.1.1",
) -> ProviderSuggestion:
    """Build a suggestion as a provider would return it."""
    return ProviderSuggestion(
        id=suggestion_id,
        suggested_name=f"Entity {suggestion_id}",
        group_id=group_id,
        group_name="Device",
        secondary_info="Channel",
        platform_options=[platform.value],
        suggestions={
            platform.value: PlatformSuggestion(
                knx={"ga_switch": {"write": address}},
                matched_group_addresses=[
                    SuggestedGroupAddress(address=address, name=f"GA {address}")
                ],
                unmatched=[],
            )
        },
        metadata={},
    )


class _StubProvider(SuggestionProvider):
    """Provider returning a fixed set of suggestions."""

    provider_id = "stub"

    @override
    async def async_get_suggestions(
        self, hass: HomeAssistant, knx: Any
    ) -> ProviderResult:
        """Return suggestions covering every filterable property."""
        return ProviderResult(
            suggestions=[
                _suggestion("light", Platform.LIGHT, "1/2/3"),
                _suggestion("cover", Platform.COVER, "1/2/4", group_id="1.1.2"),
                _suggestion("configured", Platform.LIGHT, CONFIGURED_ADDRESS),
            ],
            hints={"state": "ok"},
        )


def test_provider_requires_provider_id() -> None:
    """Test a provider without `provider_id` can not be instantiated."""

    class _IncompleteProvider(SuggestionProvider):
        @override
        async def async_get_suggestions(
            self, hass: HomeAssistant, knx: Any
        ) -> ProviderResult:
            return ProviderResult(suggestions=[], hints={})

    with pytest.raises(TypeError):
        _IncompleteProvider()  # type: ignore[abstract]


async def test_ws_get_entity_suggestions(
    knx: KNXTestKit,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test suggestions of a provider are returned with their hints."""
    await knx.setup_integration()
    with patch(
        "homeassistant.components.knx.storage.entity_suggestions.SUGGESTION_PROVIDERS",
        [_StubProvider()],
    ):
        result = await get_entity_suggestions()

    # ids are prefixed with the provider id so they stay unique across providers
    assert [suggestion["id"] for suggestion in result["suggestions"]] == [
        "stub_light",
        "stub_cover",
        "stub_configured",
    ]
    assert result["providers"] == {"stub": {"state": "ok"}}
    assert all(s["source"] == "stub" for s in result["suggestions"])
    # no entity uses these addresses yet
    assert all(not s["existing_entity_ids"] for s in result["suggestions"])


async def test_ws_get_entity_suggestions_existing_entities(
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test entities using a suggested group address are reported centrally."""
    await knx.setup_integration()
    entity = await create_ui_entity(
        Platform.SWITCH, {"ga_switch": {"write": CONFIGURED_ADDRESS}}
    )
    with patch(
        "homeassistant.components.knx.storage.entity_suggestions.SUGGESTION_PROVIDERS",
        [_StubProvider()],
    ):
        result = await get_entity_suggestions()

    by_id = {suggestion["id"]: suggestion for suggestion in result["suggestions"]}
    assert by_id["stub_configured"]["existing_entity_ids"] == [entity.entity_id]
    assert by_id["stub_light"]["existing_entity_ids"] == []


async def test_ws_get_entity_suggestions_disabled_existing_entity(
    hass: HomeAssistant,
    knx: KNXTestKit,
    entity_registry: er.EntityRegistry,
    create_ui_entity: KnxEntityGenerator,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test a disabled entity still counts as using its group addresses."""
    await knx.setup_integration()
    entity = await create_ui_entity(
        Platform.SWITCH, {"ga_switch": {"write": CONFIGURED_ADDRESS}}
    )
    entity_registry.async_update_entity(
        entity.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity.entity_id) is None

    with patch(
        "homeassistant.components.knx.storage.entity_suggestions.SUGGESTION_PROVIDERS",
        [_StubProvider()],
    ):
        result = await get_entity_suggestions()
        unconfigured = await get_entity_suggestions(include_configured=False)

    by_id = {suggestion["id"]: suggestion for suggestion in result["suggestions"]}
    assert by_id["stub_configured"]["existing_entity_ids"] == [entity.entity_id]
    assert "stub_configured" not in [
        suggestion["id"] for suggestion in unconfigured["suggestions"]
    ]


async def test_ws_get_entity_suggestions_without_providers(
    knx: KNXTestKit,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test an empty result when no provider generates suggestions."""
    await knx.setup_integration()
    with patch(
        "homeassistant.components.knx.storage.entity_suggestions.SUGGESTION_PROVIDERS",
        [],
    ):
        result = await get_entity_suggestions()

    assert result == {"suggestions": [], "providers": {}}


async def test_ws_get_entity_suggestions_filtered(
    knx: KNXTestKit,
    create_ui_entity: KnxEntityGenerator,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test narrowing down suggestions."""
    await knx.setup_integration()
    await create_ui_entity(
        Platform.SWITCH, {"ga_switch": {"write": CONFIGURED_ADDRESS}}
    )
    with patch(
        "homeassistant.components.knx.storage.entity_suggestions.SUGGESTION_PROVIDERS",
        [_StubProvider()],
    ):
        by_platform = await get_entity_suggestions(platform=Platform.COVER)
        by_group = await get_entity_suggestions(group_id="1.1.1")
        unconfigured = await get_entity_suggestions(include_configured=False)

    assert [suggestion["id"] for suggestion in by_platform["suggestions"]] == [
        "stub_cover"
    ]
    # hints are reported no matter how narrow the filter is
    assert by_platform["providers"] == {"stub": {"state": "ok"}}

    assert [suggestion["id"] for suggestion in by_group["suggestions"]] == [
        "stub_light",
        "stub_configured",
    ]
    # suggestions whose group addresses are already used are dropped
    assert [suggestion["id"] for suggestion in unconfigured["suggestions"]] == [
        "stub_light",
        "stub_cover",
    ]


PROVIDERS_PATH = (
    "homeassistant.components.knx.storage.entity_suggestions.SUGGESTION_PROVIDERS"
)


def _entity_suggestion(
    suggestion_id: str,
    configs: dict[Platform, dict[str, Any]],
    group_id: str = "1.1.1",
    unmatched_addresses: tuple[str, ...] = (),
) -> ProviderSuggestion:
    """Build a suggestion of a `ga_switch` config for each platform."""
    return ProviderSuggestion(
        id=suggestion_id,
        suggested_name=f"Entity {suggestion_id}",
        group_id=group_id,
        group_name=f"Group {group_id}",
        secondary_info="",
        platform_options=[platform.value for platform in configs],
        suggestions={
            platform.value: PlatformSuggestion(
                knx={"section": {"ga_switch": ga_config}},
                matched_group_addresses=[
                    SuggestedGroupAddress(address=address, name=f"GA {address}")
                    for address in (
                        ga_config.get("write"),
                        ga_config.get("state"),
                        *ga_config.get("passive", ()),
                    )
                    if address is not None and address not in unmatched_addresses
                ],
                unmatched=[],
            )
            for platform, ga_config in configs.items()
        },
        metadata={},
    )


def _provider(provider_id: str, *suggestions: ProviderSuggestion) -> SuggestionProvider:
    """Create a provider returning fixed suggestions."""

    class _Provider(SuggestionProvider):
        @property
        @override
        def provider_id(self) -> str:
            return provider_id

        @override
        async def async_get_suggestions(
            self, hass: HomeAssistant, knx: Any
        ) -> ProviderResult:
            return ProviderResult(suggestions=list(suggestions), hints={})

    return _Provider()


def _by_id(result: dict[str, Any]) -> dict[str, Any]:
    return {suggestion["id"]: suggestion for suggestion in result["suggestions"]}


async def test_duplicates_of_providers(
    knx: KNXTestKit,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test suggestions of providers for the same thing are linked and ranked."""
    await knx.setup_integration()
    light = {"write": "1/0/1", "state": "1/0/2"}
    providers = [
        _provider("high", _entity_suggestion("a", {Platform.LIGHT: light})),
        _provider(
            "mid",
            _entity_suggestion(
                "b",
                # the default platform has no counterpart
                {Platform.SWITCH: light, Platform.LIGHT: light},
                group_id="1.1.2",
            ),
        ),
        _provider(
            "low",
            _entity_suggestion(
                "c", {Platform.LIGHT: {"write": "1/0/1"}}, group_id="room"
            ),
        ),
    ]
    with patch(PROVIDERS_PATH, providers):
        result = await get_entity_suggestions()

    # ordered by the rank of the providers
    assert list(suggestions := _by_id(result)) == ["high_a", "mid_b", "low_c"]
    assert suggestions["high_a"]["superseded_by"] is None
    assert suggestions["high_a"]["duplicates"] == [
        {
            "id": "mid_b",
            "source": "mid",
            "suggested_name": "Entity b",
            "group_id": "1.1.2",
            "group_name": "Group 1.1.2",
            "platforms": ["light"],
            # only the address written to identifies the entity
            "group_addresses": ["1/0/1"],
        },
        {
            "id": "low_c",
            "source": "low",
            "suggested_name": "Entity c",
            "group_id": "room",
            "group_name": "Group room",
            "platforms": ["light"],
            "group_addresses": ["1/0/1"],
        },
    ]
    assert suggestions["mid_b"]["superseded_by"] == "high_a"
    assert [d["id"] for d in suggestions["mid_b"]["duplicates"]] == ["high_a", "low_c"]
    # superseded by the most reliable of its duplicates
    assert suggestions["low_c"]["superseded_by"] == "high_a"
    assert [d["id"] for d in suggestions["low_c"]["duplicates"]] == ["high_a", "mid_b"]


@pytest.mark.parametrize(
    ("high", "low", "shared_addresses"),
    [
        # a status may be shared - eg. a common feedback of separate commands
        (
            {Platform.LIGHT: {"write": "1/0/1", "state": "1/0/9"}},
            {Platform.LIGHT: {"write": "1/0/2", "state": "1/0/9"}},
            None,
        ),
        # one's status is not what another one writes to
        (
            {Platform.LIGHT: {"write": "1/0/1", "state": "1/0/2"}},
            {Platform.LIGHT: {"write": "1/0/2"}},
            None,
        ),
        # passive addresses don't identify an entity
        (
            {Platform.LIGHT: {"write": "1/0/1", "passive": ["1/0/3"]}},
            {Platform.LIGHT: {"write": "1/0/2", "passive": ["1/0/3"]}},
            None,
        ),
        # another platform is another entity
        (
            {Platform.LIGHT: {"write": "1/0/1"}},
            {Platform.SWITCH: {"write": "1/0/1"}},
            None,
        ),
        # without anything written, the status identifies the entity
        (
            {Platform.BINARY_SENSOR: {"state": "1/0/2"}},
            {Platform.BINARY_SENSOR: {"state": "1/0/2", "passive": ["1/0/3"]}},
            ["1/0/2"],
        ),
        (
            {Platform.BINARY_SENSOR: {"state": "1/0/2"}},
            {Platform.LIGHT: {"write": "1/0/1", "state": "1/0/2"}},
            None,
        ),
    ],
)
async def test_duplicate_identification(
    knx: KNXTestKit,
    get_entity_suggestions: KnxSuggestionGetter,
    high: dict[Platform, dict[str, Any]],
    low: dict[Platform, dict[str, Any]],
    shared_addresses: list[str] | None,
) -> None:
    """Test which group addresses make suggestions duplicates."""
    await knx.setup_integration()
    providers = [
        _provider("high", _entity_suggestion("a", high)),
        _provider("low", _entity_suggestion("b", low)),
    ]
    with patch(PROVIDERS_PATH, providers):
        suggestions = _by_id(await get_entity_suggestions())

    if shared_addresses is None:
        assert suggestions["high_a"]["duplicates"] == []
        assert suggestions["low_b"]["duplicates"] == []
        assert suggestions["low_b"]["superseded_by"] is None
        return
    assert [d["group_addresses"] for d in suggestions["high_a"]["duplicates"]] == [
        shared_addresses
    ]
    assert suggestions["low_b"]["superseded_by"] == "high_a"


async def test_no_duplicates_within_a_provider_or_on_unmatched_addresses(
    knx: KNXTestKit,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test alternatives of a provider and unreported addresses are not linked."""
    await knx.setup_integration()
    providers = [
        _provider(
            "high",
            _entity_suggestion("a", {Platform.LIGHT: {"write": "1/0/1"}}),
            _entity_suggestion("b", {Platform.LIGHT: {"write": "1/0/1"}}),
            # an address the provider doesn't report as matched - eg. a central
            # function shared by all its suggestions
            _entity_suggestion(
                "c",
                {Platform.LIGHT: {"write": "1/0/5"}},
                unmatched_addresses=("1/0/5",),
            ),
        ),
        _provider(
            "low",
            _entity_suggestion("d", {Platform.LIGHT: {"write": "1/0/5"}}),
        ),
    ]
    with patch(PROVIDERS_PATH, providers):
        suggestions = _by_id(await get_entity_suggestions())

    assert all(not suggestion["duplicates"] for suggestion in suggestions.values())
    assert all(
        suggestion["superseded_by"] is None for suggestion in suggestions.values()
    )


async def test_duplicates_filtered(
    knx: KNXTestKit,
    get_entity_suggestions: KnxSuggestionGetter,
) -> None:
    """Test duplicates are reported for and dropped from filtered responses."""
    await knx.setup_integration()
    providers = [
        _provider(
            "high",
            _entity_suggestion("a", {Platform.LIGHT: {"write": "1/0/1"}}),
            _entity_suggestion("b", {Platform.SWITCH: {"write": "1/0/2"}}),
        ),
        _provider(
            "low",
            _entity_suggestion(
                "c", {Platform.LIGHT: {"write": "1/0/1"}}, group_id="room"
            ),
            _entity_suggestion(
                "d", {Platform.LIGHT: {"write": "1/0/3"}}, group_id="room"
            ),
        ),
    ]
    with patch(PROVIDERS_PATH, providers):
        unique = await get_entity_suggestions(include_superseded=False)
        room = await get_entity_suggestions(group_id="room")
        unique_room = await get_entity_suggestions(
            group_id="room", include_superseded=False
        )
        unique_lights = await get_entity_suggestions(
            platform=Platform.LIGHT, include_superseded=False
        )

    # every suggested entity once - from the most reliable provider
    assert list(_by_id(unique)) == ["high_a", "high_b", "low_d"]
    # the duplicate left out is still reported
    assert [d["id"] for d in _by_id(unique)["high_a"]["duplicates"]] == ["low_c"]

    # duplicates are found before filtering: the one of another group is reported
    assert list(_by_id(room)) == ["low_c", "low_d"]
    assert _by_id(room)["low_c"]["superseded_by"] == "high_a"
    assert _by_id(room)["low_c"]["duplicates"][0]["group_id"] == "1.1.1"
    # a suggestion is not dropped for one that is not returned
    assert list(_by_id(unique_room)) == ["low_c", "low_d"]
    assert list(_by_id(unique_lights)) == ["high_a", "low_d"]


def _com_object(dpa: str, address: str, receives: bool) -> dict[str, Any]:
    return {
        "dpas": [dpa],
        "group_address_links": [address],
        "flags": {
            "read": not receives,
            "write": receives,
            "communication": True,
            "transmit": not receives,
            "update": False,
            "read_on_init": False,
        },
    }


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
        "usage_text": "",
    }


# an actuator with functional block semantics, whose first channel is also
# described by a function of the kitchen
TEST_PROJECT: dict[str, Any] = {
    "info": {"xknxproject_version": "3.10.0", "group_address_style": "ThreeLevel"},
    "group_addresses": {
        address: {
            "name": f"GA {address}",
            "address": address,
            "description": "",
            "dpt": {"main": 1, "sub": 1},
        }
        for address in ("1/0/1", "1/0/2", "1/0/3", "1/0/4", "1/0/5")
    },
    "devices": {
        "1.1.1": {
            "name": "Switch actuator",
            "channels": {
                "CH-1": {
                    "identifier": "CH-1",
                    "name": "Output A",
                    "communication_object_ids": ["co-1", "co-2"],
                    "functional_blocks": ["417"],
                },
                "CH-2": {
                    "identifier": "CH-2",
                    "name": "Output B",
                    "communication_object_ids": ["co-3", "co-4"],
                    "functional_blocks": ["417"],
                },
            },
        },
    },
    "communication_objects": {
        "co-1": _com_object("417.52", "1/0/1", receives=True),
        "co-2": _com_object("417.51", "1/0/2", receives=False),
        "co-3": _com_object("417.52", "1/0/3", receives=True),
        # the status of output A is linked to output B too
        "co-4": _com_object("417.51", "1/0/2", receives=False),
    },
    "locations": {
        "P-1": {
            "type": "Room",
            "identifier": "P-1",
            "name": "Kitchen",
            "usage_id": None,
            "usage_text": "",
            "number": "",
            "description": "",
            "project_uid": None,
            "devices": [],
            "spaces": {},
            "functions": [],
        }
    },
    "functions": {
        "F-1": _function(
            "Ceiling light",
            "FT-1",
            "P-1",
            ("1/0/1", "SwitchOnOff"),
            ("1/0/2", "InfoOnOff"),
        ),
        # no channel with semantics is on these addresses
        "F-2": _function(
            "Socket",
            "FT-10",
            "P-1",
            ("1/0/4", "SwitchOnOff"),
            ("1/0/5", "InfoOnOff"),
        ),
    },
}


async def test_functional_block_and_function_duplicates(
    knx: KNXTestKit,
    get_entity_suggestions: KnxSuggestionGetter,
    hass_storage: dict[str, Any],
) -> None:
    """Test a channel and a function sharing group addresses are linked."""
    hass_storage[KNX_PROJECT_STORAGE_KEY] = {"version": 1, "data": TEST_PROJECT}
    await knx.setup_integration()

    result = await get_entity_suggestions()
    # ranked by provider - the provider of existing configurations has none
    assert list(result["providers"]) == ["cfg", "fb", "function"]
    suggestions = _by_id(result)
    assert list(suggestions) == [
        "fb_1.1.1_CH-1",
        "fb_1.1.1_CH-2",
        "function_F-1",
        "function_F-2",
    ]

    channel = suggestions["fb_1.1.1_CH-1"]
    function = suggestions["function_F-1"]
    assert (
        channel["suggestions"]["light"]["knx"]["ga_switch"]["write"]
        == function["suggestions"]["light"]["knx"]["ga_switch"]["write"]
        == "1/0/1"
    )
    # the functional block is preferred - the function has the name and room
    assert channel["superseded_by"] is None
    assert channel["duplicates"] == [
        {
            "id": "function_F-1",
            "source": "function",
            "suggested_name": "Ceiling light",
            "group_id": "P-1",
            "group_name": "Kitchen",
            # the channel could also be a switch, the function is a light
            "platforms": ["light"],
            "group_addresses": ["1/0/1"],
        }
    ]
    assert function["superseded_by"] == "fb_1.1.1_CH-1"
    assert function["duplicates"] == [
        {
            "id": "fb_1.1.1_CH-1",
            "source": "fb",
            "suggested_name": "Output A",
            "group_id": "1.1.1",
            "group_name": "Switch actuator",
            "platforms": ["light"],
            "group_addresses": ["1/0/1"],
        }
    ]
    # sharing a status address only is no duplicate
    assert suggestions["fb_1.1.1_CH-2"]["duplicates"] == []
    assert suggestions["function_F-2"]["duplicates"] == []
    assert suggestions["function_F-2"]["superseded_by"] is None

    # a room is not emptied of suggestions preferred ones of its devices replace
    room = await get_entity_suggestions(group_id="P-1", include_superseded=False)
    assert list(_by_id(room)) == ["function_F-1", "function_F-2"]
    unique = await get_entity_suggestions(include_superseded=False)
    assert list(_by_id(unique)) == [
        "fb_1.1.1_CH-1",
        "fb_1.1.1_CH-2",
        "function_F-2",
    ]
