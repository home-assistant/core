"""LLM tools for the media_player integration."""

from typing import Any, cast, override

import probatio

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, intent
from homeassistant.helpers.llm import (
    LLM_API_ASSIST,
    IntentTool,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
    async_get_match_preferences,
)
from homeassistant.util.json import JsonValueType

from .browse_media import SearchMedia
from .const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_FILTER_CLASSES,
    ATTR_MEDIA_SEARCH_QUERY,
    DOMAIN,
    INTENT_MEDIA_NEXT,
    INTENT_MEDIA_PAUSE,
    INTENT_MEDIA_PREVIOUS,
    INTENT_MEDIA_UNPAUSE,
    INTENT_PLAYER_MUTE,
    INTENT_PLAYER_UNMUTE,
    INTENT_SET_VOLUME,
    INTENT_SET_VOLUME_RELATIVE,
    SERVICE_PLAY_MEDIA,
    SERVICE_SEARCH_MEDIA,
    MediaClass,
    MediaPlayerEntityFeature,
)

# Intents owned by this integration that are exposed as LLM tools.
LLM_INTENTS = {
    INTENT_MEDIA_NEXT: "Next track",
    INTENT_MEDIA_PAUSE: "Pause media",
    INTENT_PLAYER_MUTE: "Mute player",
    INTENT_PLAYER_UNMUTE: "Unmute player",
    INTENT_MEDIA_PREVIOUS: "Previous track",
    INTENT_MEDIA_UNPAUSE: "Resume media",
    INTENT_SET_VOLUME: "Set volume",
    INTENT_SET_VOLUME_RELATIVE: "Change volume",
}

# Setting a value on the user's own player has no further effect when it is
# repeated. Stepping through tracks or volume has an effect on every call.
_CONTROL = ToolAnnotations(idempotent=True, open_world=False)
_CUMULATIVE = ToolAnnotations(open_world=False)

INTENT_ANNOTATIONS = {
    INTENT_MEDIA_PAUSE: _CONTROL,
    # Unpausing clears the players it remembered, so a repeat can resume more.
    INTENT_MEDIA_UNPAUSE: _CUMULATIVE,
    INTENT_PLAYER_MUTE: _CONTROL,
    INTENT_PLAYER_UNMUTE: _CONTROL,
    INTENT_SET_VOLUME: _CONTROL,
    INTENT_MEDIA_NEXT: _CUMULATIVE,
    INTENT_MEDIA_PREVIOUS: _CUMULATIVE,
    INTENT_SET_VOLUME_RELATIVE: _CUMULATIVE,
}

# Both tools match players with the same features, so the same target
# arguments resolve to the same player. Search results are only valid on the
# player that returned them.
SEARCH_PLAY_FEATURES = (
    MediaPlayerEntityFeature.SEARCH_MEDIA | MediaPlayerEntityFeature.PLAY_MEDIA
)

TARGET_SCHEMA = {
    probatio.Optional("name"): cv.string,
    probatio.Optional("area"): cv.string,
    probatio.Optional("floor"): cv.string,
}


def _validate_args(
    schema: probatio.Schema, tool_args: dict[str, Any]
) -> dict[str, Any]:
    """Validate tool arguments, omitting the blank values that LLMs often send."""
    args: dict[str, Any] = schema(
        {
            key: value
            for key, value in tool_args.items()
            if not intent.is_blank_slot_value(value)
        }
    )
    return args


@callback
def _async_match_player(
    hass: HomeAssistant, llm_context: LLMContext, args: dict[str, Any]
) -> State:
    """Return the single media player that the target arguments match."""
    constraints = intent.MatchTargetsConstraints(
        name=args.get("name"),
        area_name=args.get("area"),
        floor_name=args.get("floor"),
        domains={DOMAIN},
        assistant=llm_context.assistant,
        features=SEARCH_PLAY_FEATURES,
        single_target=True,
    )
    preferences = async_get_match_preferences(hass, llm_context)
    result = intent.async_match_targets(hass, constraints, preferences)
    if not result.is_match:
        raise intent.MatchFailedError(
            result=result, constraints=constraints, preferences=preferences
        )
    return result.states[0]


class MediaSearchTool(Tool):
    """LLM Tool that searches a media player for media."""

    name = "media_player__search_media"
    title = "Search media"
    description = "Searches a media player for media and returns the playable items."
    parameters = probatio.Schema(
        {
            probatio.Required(
                ATTR_MEDIA_SEARCH_QUERY,
                description="What to search for, such as a song, artist or album",
            ): cv.string,
            probatio.Optional(
                "media_class", description="Only return media of this class"
            ): probatio.In([cls.value for cls in MediaClass]),
            **TARGET_SCHEMA,
        }
    )
    annotations = ToolAnnotations(read_only=True, destructive=False, idempotent=True)
    integration = DOMAIN

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Search a media player."""
        args = _validate_args(self.parameters, tool_input.tool_args)
        entity_id = _async_match_player(hass, llm_context, args).entity_id

        service_data: dict[str, Any] = {
            ATTR_ENTITY_ID: entity_id,
            ATTR_MEDIA_SEARCH_QUERY: args[ATTR_MEDIA_SEARCH_QUERY],
        }
        if media_class := args.get("media_class"):
            service_data[ATTR_MEDIA_FILTER_CLASSES] = [media_class]

        service_result = await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH_MEDIA,
            service_data,
            context=llm_context.context,
            blocking=True,
            return_response=True,
        )
        search_media = cast(dict[str, SearchMedia], service_result)[entity_id]
        results: list[JsonValueType] = [
            {
                "title": item.title,
                "media_class": item.media_class,
                ATTR_MEDIA_CONTENT_TYPE: item.media_content_type,
                ATTR_MEDIA_CONTENT_ID: item.media_content_id,
            }
            for item in search_media.result
            if item.can_play
        ]
        if not results:
            return ToolResult(data={"results": results})
        return ToolResult(
            data={
                "results": results,
                "instruction": (
                    "Pick the result that best matches the request. "
                    f"Call {MediaPlayTool.name} with its media_content_id and "
                    "media_content_type, and with the same name, area and floor "
                    "as this search."
                ),
            }
        )


class MediaPlayTool(Tool):
    """LLM Tool that plays a media item found by the search media tool."""

    name = "media_player__play_media"
    title = "Play media"
    description = (
        "Plays a media item that the search media tool returned, or a URL. "
        "For a search result, pass the same name, area and floor as the search."
    )
    parameters = probatio.Schema(
        {
            probatio.Required(
                ATTR_MEDIA_CONTENT_ID,
                description="The media_content_id of the search result, or a URL",
            ): cv.string,
            probatio.Required(
                ATTR_MEDIA_CONTENT_TYPE,
                description=(
                    "The media_content_type of the search result. "
                    "Use music to play an audio URL."
                ),
            ): cv.string,
            **TARGET_SCHEMA,
        }
    )
    integration = DOMAIN

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Play a media item."""
        args = _validate_args(self.parameters, tool_input.tool_args)
        entity_id = _async_match_player(hass, llm_context, args).entity_id

        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_MEDIA_CONTENT_ID: args[ATTR_MEDIA_CONTENT_ID],
                ATTR_MEDIA_CONTENT_TYPE: args[ATTR_MEDIA_CONTENT_TYPE],
            },
            context=llm_context.context,
            blocking=True,
        )
        return ToolResult(data={"success": True})


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return LLM tools for the integration when its domain is exposed."""
    if api_id != LLM_API_ASSIST:
        return None

    if not llm_context.assistant:
        return None

    exposed = [
        state
        for state in hass.states.async_all(DOMAIN)
        if async_should_expose(hass, llm_context.assistant, state.entity_id)
    ]
    if not exposed:
        return None

    tools: list[Tool] = [
        IntentTool(
            f"{DOMAIN}__{handler.intent_type}",
            handler,
            title=LLM_INTENTS[handler.intent_type],
            integration=DOMAIN,
            annotations=INTENT_ANNOTATIONS[handler.intent_type],
        )
        for handler in intent.async_get(hass)
        if handler.intent_type in LLM_INTENTS
    ]
    if any(
        state.attributes.get(ATTR_SUPPORTED_FEATURES, 0) & SEARCH_PLAY_FEATURES
        == SEARCH_PLAY_FEATURES
        for state in exposed
    ):
        tools.extend([MediaSearchTool(), MediaPlayTool()])
    return LLMTools(tools=tools)
