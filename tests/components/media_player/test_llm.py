"""Tests for the media_player LLM tools platform."""

from typing import Any

import probatio
import pytest

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.media_player import (
    DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SEARCH_MEDIA,
    BrowseMedia,
    MediaClass,
    MediaPlayerEntityFeature,
    MediaType,
    SearchMedia,
    llm as media_player_llm,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    intent,
    llm,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_mock_service

ENTITY_ID = "media_player.test"
SEARCH_PLAY_FEATURES = (
    MediaPlayerEntityFeature.SEARCH_MEDIA | MediaPlayerEntityFeature.PLAY_MEDIA
)
INTENT_TOOL_NAMES = {
    "media_player__HassMediaNext",
    "media_player__HassMediaPause",
    "media_player__HassMediaPlayerMute",
    "media_player__HassMediaPlayerUnmute",
    "media_player__HassMediaPrevious",
    "media_player__HassMediaUnpause",
    "media_player__HassSetVolume",
    "media_player__HassSetVolumeRelative",
}
SEARCH_PLAY_TOOL_NAMES = {"media_player__search_media", "media_player__play_media"}
TOOL_NAMES = INTENT_TOOL_NAMES | SEARCH_PLAY_TOOL_NAMES

TRACK = BrowseMedia(
    title="Queen - Bohemian Rhapsody",
    media_class=MediaClass.TRACK,
    media_content_type=MediaType.TRACK,
    media_content_id="library://track/1",
    can_play=True,
    can_expand=False,
)
ALBUM = BrowseMedia(
    title="A Night at the Opera",
    media_class=MediaClass.ALBUM,
    media_content_type=MediaType.ALBUM,
    media_content_id="library://album/2",
    can_play=True,
    can_expand=True,
)
ARTIST = BrowseMedia(
    title="Queen",
    media_class=MediaClass.ARTIST,
    media_content_type=MediaType.ARTIST,
    media_content_id="library://artist/3",
    can_play=False,
    can_expand=True,
)


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations and expose a media_player entity."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "media_player", {})
    assert await async_setup_component(hass, "llm", {})
    hass.states.async_set(
        ENTITY_ID,
        "idle",
        {
            "friendly_name": "Test media_player",
            ATTR_SUPPORTED_FEATURES: SEARCH_PLAY_FEATURES,
        },
    )
    async_expose_entity(hass, "conversation", ENTITY_ID, True)
    await hass.async_block_till_done()


def _llm_context(device_id: str | None = None) -> llm.LLMContext:
    """Return an LLM context for the conversation assistant."""
    return llm.LLMContext(
        platform="test_platform",
        context=Context(),
        language="*",
        assistant="conversation",
        device_id=device_id,
    )


async def _tool_names(hass: HomeAssistant) -> set[str]:
    """Return the names of the tools offered by the media_player platform."""
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    return {tool.name for tool in result.tools}


async def _async_call_tool(
    hass: HomeAssistant,
    tool_name: str,
    tool_args: dict[str, Any],
    device_id: str | None = None,
) -> llm.ToolResult:
    """Call a tool through the Assist API."""
    api = await llm.async_get_api(hass, "assist", _llm_context(device_id))
    return await api.async_call_tool(
        llm.ToolInput(tool_name=tool_name, tool_args=tool_args)
    )


async def test_tools_exposed(hass: HomeAssistant) -> None:
    """Test the tools are offered for an exposed media_player entity."""
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    tools = {tool.name: tool for tool in result.tools}
    assert tools.keys() >= TOOL_NAMES
    assert "media_player__HassMediaSearchAndPlay" not in tools

    control = llm.ToolAnnotations(idempotent=True, open_world=False)
    repeats = llm.ToolAnnotations(open_world=False)
    assert {
        name: (tool.title, tool.integration, tool.annotations)
        for name, tool in tools.items()
        if name in TOOL_NAMES
    } == {
        "media_player__HassMediaNext": ("Next track", "media_player", repeats),
        "media_player__HassMediaPause": ("Pause media", "media_player", control),
        "media_player__HassMediaPlayerMute": ("Mute player", "media_player", control),
        "media_player__HassMediaPlayerUnmute": (
            "Unmute player",
            "media_player",
            control,
        ),
        "media_player__HassMediaPrevious": ("Previous track", "media_player", repeats),
        "media_player__HassMediaUnpause": ("Resume media", "media_player", repeats),
        "media_player__HassSetVolume": ("Set volume", "media_player", control),
        "media_player__HassSetVolumeRelative": (
            "Change volume",
            "media_player",
            repeats,
        ),
        "media_player__search_media": (
            "Search media",
            "media_player",
            llm.ToolAnnotations(read_only=True, destructive=False, idempotent=True),
        ),
        "media_player__play_media": (
            "Play media",
            "media_player",
            llm.ToolAnnotations(),
        ),
    }


async def test_tools_not_exposed(hass: HomeAssistant) -> None:
    """Test the tools are hidden when no media_player entity is exposed."""
    async_expose_entity(hass, "conversation", ENTITY_ID, False)
    assert not TOOL_NAMES & await _tool_names(hass)
    assert media_player_llm.async_get_tools(hass, _llm_context(), "assist") is None


@pytest.mark.parametrize(
    "supported_features",
    [
        pytest.param(0, id="none"),
        pytest.param(MediaPlayerEntityFeature.SEARCH_MEDIA, id="search_only"),
        pytest.param(MediaPlayerEntityFeature.PLAY_MEDIA, id="play_only"),
    ],
)
async def test_search_play_tools_need_features(
    hass: HomeAssistant, supported_features: MediaPlayerEntityFeature
) -> None:
    """Test the search and play tools need a player that can search and play."""
    hass.states.async_set(
        ENTITY_ID, "idle", {ATTR_SUPPORTED_FEATURES: supported_features}
    )
    tool_names = await _tool_names(hass)
    assert tool_names >= INTENT_TOOL_NAMES
    assert not SEARCH_PLAY_TOOL_NAMES & tool_names


async def test_no_tools_for_other_api(hass: HomeAssistant) -> None:
    """Test the platform returns None for an unsupported API."""
    assert media_player_llm.async_get_tools(hass, _llm_context(), "other") is None


@pytest.mark.parametrize(
    ("tool_args", "service_data"),
    [
        pytest.param(
            {"search_query": "queen"},
            {"entity_id": ENTITY_ID, "search_query": "queen"},
            id="query",
        ),
        pytest.param(
            {"search_query": "queen", "media_class": "album"},
            {
                "entity_id": ENTITY_ID,
                "search_query": "queen",
                "media_filter_classes": ["album"],
            },
            id="media_class",
        ),
    ],
)
async def test_search_media(
    hass: HomeAssistant, tool_args: dict[str, Any], service_data: dict[str, Any]
) -> None:
    """Test the search tool returns the playable results of the player."""
    search_calls = async_mock_service(
        hass,
        DOMAIN,
        SERVICE_SEARCH_MEDIA,
        response={ENTITY_ID: SearchMedia(result=[TRACK, ARTIST, ALBUM])},
    )

    result = await _async_call_tool(hass, "media_player__search_media", tool_args)

    assert result == llm.ToolResult(
        data={
            "results": [
                {
                    "title": "Queen - Bohemian Rhapsody",
                    "media_class": "track",
                    "media_content_type": "track",
                    "media_content_id": "library://track/1",
                },
                {
                    "title": "A Night at the Opera",
                    "media_class": "album",
                    "media_content_type": "album",
                    "media_content_id": "library://album/2",
                },
            ],
            "instruction": (
                "Pick the result that best matches the request. "
                "Call media_player__play_media with its media_content_id and "
                "media_content_type, and with the same name, area and floor "
                "as this search."
            ),
        }
    )
    assert len(search_calls) == 1
    assert search_calls[0].data == service_data


async def test_search_media_limits_results(hass: HomeAssistant) -> None:
    """Test the search tool returns at most 20 playable results."""
    tracks = [
        BrowseMedia(
            title=f"Track {index}",
            media_class=MediaClass.TRACK,
            media_content_type=MediaType.TRACK,
            media_content_id=f"library://track/{index}",
            can_play=True,
            can_expand=False,
        )
        for index in range(25)
    ]
    async_mock_service(
        hass,
        DOMAIN,
        SERVICE_SEARCH_MEDIA,
        response={ENTITY_ID: SearchMedia(result=[ARTIST, *tracks])},
    )

    result = await _async_call_tool(
        hass, "media_player__search_media", {"search_query": "track"}
    )

    assert [item["title"] for item in result.data["results"]] == [
        f"Track {index}" for index in range(20)
    ]


async def test_search_media_no_results(hass: HomeAssistant) -> None:
    """Test the search tool returns an empty list when nothing matches."""
    async_mock_service(
        hass,
        DOMAIN,
        SERVICE_SEARCH_MEDIA,
        response={ENTITY_ID: SearchMedia(result=[])},
    )

    result = await _async_call_tool(
        hass, "media_player__search_media", {"search_query": "nothing"}
    )

    assert result == llm.ToolResult(data={"results": []})


async def test_search_media_invalid_media_class(hass: HomeAssistant) -> None:
    """Test the search tool rejects an unknown media class."""
    search_calls = async_mock_service(hass, DOMAIN, SERVICE_SEARCH_MEDIA)

    with pytest.raises(probatio.Invalid):
        await _async_call_tool(
            hass,
            "media_player__search_media",
            {"search_query": "queen", "media_class": "invalid"},
        )
    assert not search_calls


@pytest.mark.parametrize(
    "media",
    [
        pytest.param(
            {"media_content_id": "library://album/2", "media_content_type": "album"},
            id="search_result",
        ),
        pytest.param(
            {
                "media_content_id": "https://example.com/stream.mp3",
                "media_content_type": "music",
            },
            id="url",
        ),
    ],
)
async def test_play_media(hass: HomeAssistant, media: dict[str, str]) -> None:
    """Test the play tool plays the chosen item on the player."""
    play_calls = async_mock_service(hass, DOMAIN, SERVICE_PLAY_MEDIA)

    result = await _async_call_tool(
        hass, "media_player__play_media", {**media, "name": "Test media_player"}
    )

    assert result == llm.ToolResult(data={"success": True})
    assert len(play_calls) == 1
    assert play_calls[0].data == {"entity_id": ENTITY_ID, **media}


async def test_blank_target_values_omitted(hass: HomeAssistant) -> None:
    """Test the tools treat blank target values as omitted."""
    search_calls = async_mock_service(
        hass,
        DOMAIN,
        SERVICE_SEARCH_MEDIA,
        response={ENTITY_ID: SearchMedia(result=[])},
    )
    play_calls = async_mock_service(hass, DOMAIN, SERVICE_PLAY_MEDIA)
    blank_target = {"name": "", "area": " ", "floor": None}

    await _async_call_tool(
        hass,
        "media_player__search_media",
        {"search_query": "queen", "media_class": "", **blank_target},
    )
    await _async_call_tool(
        hass,
        "media_player__play_media",
        {
            "media_content_id": "library://album/2",
            "media_content_type": "album",
            **blank_target,
        },
    )

    assert search_calls[0].data == {"entity_id": ENTITY_ID, "search_query": "queen"}
    assert play_calls[0].data["entity_id"] == ENTITY_ID


@pytest.mark.parametrize(
    ("tool_name", "tool_args"),
    [
        pytest.param(
            "media_player__search_media", {"search_query": "queen"}, id="search"
        ),
        pytest.param(
            "media_player__play_media",
            {"media_content_id": "library://album/2", "media_content_type": "album"},
            id="play",
        ),
    ],
)
async def test_player_without_features_not_matched(
    hass: HomeAssistant, tool_name: str, tool_args: dict[str, Any]
) -> None:
    """Test the tools only target a player that can search and play."""
    hass.states.async_set(
        "media_player.play_only",
        "idle",
        {
            "friendly_name": "Play only",
            ATTR_SUPPORTED_FEATURES: MediaPlayerEntityFeature.PLAY_MEDIA,
        },
    )
    async_expose_entity(hass, "conversation", "media_player.play_only", True)
    search_calls = async_mock_service(hass, DOMAIN, SERVICE_SEARCH_MEDIA)
    play_calls = async_mock_service(hass, DOMAIN, SERVICE_PLAY_MEDIA)

    with pytest.raises(intent.MatchFailedError):
        await _async_call_tool(hass, tool_name, {**tool_args, "name": "Play only"})
    assert not search_calls
    assert not play_calls


async def test_search_and_play_use_device_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test search and play target the player in the area of the device."""
    kitchen = area_registry.async_create("Kitchen")
    bedroom = area_registry.async_create("Bedroom")

    for area in (kitchen, bedroom):
        entry = entity_registry.async_get_or_create(
            DOMAIN, "test", area.id, suggested_object_id=area.id
        )
        entity_registry.async_update_entity(entry.entity_id, area_id=area.id)
        hass.states.async_set(
            entry.entity_id,
            "idle",
            {
                "friendly_name": f"{area.name} speaker",
                ATTR_SUPPORTED_FEATURES: SEARCH_PLAY_FEATURES,
            },
        )
        async_expose_entity(hass, "conversation", entry.entity_id, True)

    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    satellite = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:78:90:ab")},
    )
    device_registry.async_update_device(satellite.id, area_id=bedroom.id)

    search_calls = async_mock_service(
        hass,
        DOMAIN,
        SERVICE_SEARCH_MEDIA,
        response={"media_player.bedroom": SearchMedia(result=[TRACK])},
    )
    play_calls = async_mock_service(hass, DOMAIN, SERVICE_PLAY_MEDIA)

    result = await _async_call_tool(
        hass,
        "media_player__search_media",
        {"search_query": "bohemian rhapsody"},
        device_id=satellite.id,
    )
    item = result.data["results"][0]
    await _async_call_tool(
        hass,
        "media_player__play_media",
        {
            "media_content_id": item["media_content_id"],
            "media_content_type": item["media_content_type"],
        },
        device_id=satellite.id,
    )

    assert search_calls[0].data["entity_id"] == "media_player.bedroom"
    assert play_calls[0].data == {
        "entity_id": "media_player.bedroom",
        "media_content_id": "library://track/1",
        "media_content_type": "track",
    }
