"""LLM tools for the media_player integration."""

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent
from homeassistant.helpers.llm import (
    LLM_API_ASSIST,
    IntentTool,
    LLMContext,
    Tool,
    ToolAnnotations,
)

from .const import (
    DOMAIN,
    INTENT_MEDIA_NEXT,
    INTENT_MEDIA_PAUSE,
    INTENT_MEDIA_PREVIOUS,
    INTENT_MEDIA_SEARCH_AND_PLAY,
    INTENT_MEDIA_UNPAUSE,
    INTENT_PLAYER_MUTE,
    INTENT_PLAYER_UNMUTE,
    INTENT_SET_VOLUME,
    INTENT_SET_VOLUME_RELATIVE,
)

# Intents owned by this integration that are exposed as LLM tools.
LLM_INTENTS = (
    INTENT_MEDIA_NEXT,
    INTENT_MEDIA_PAUSE,
    INTENT_PLAYER_MUTE,
    INTENT_PLAYER_UNMUTE,
    INTENT_MEDIA_PREVIOUS,
    INTENT_MEDIA_SEARCH_AND_PLAY,
    INTENT_MEDIA_UNPAUSE,
    INTENT_SET_VOLUME,
    INTENT_SET_VOLUME_RELATIVE,
)

# Setting a value on the user's own player has no further effect when it is
# repeated. Stepping through tracks or volume has an effect on every call, and
# a search reaches the media the player can read.
_CONTROL = ToolAnnotations(idempotent=True, open_world=False)
_CUMULATIVE = ToolAnnotations(open_world=False)

INTENT_ANNOTATIONS = {
    INTENT_MEDIA_PAUSE: _CONTROL,
    INTENT_MEDIA_UNPAUSE: _CONTROL,
    INTENT_PLAYER_MUTE: _CONTROL,
    INTENT_PLAYER_UNMUTE: _CONTROL,
    INTENT_SET_VOLUME: _CONTROL,
    INTENT_MEDIA_NEXT: _CUMULATIVE,
    INTENT_MEDIA_PREVIOUS: _CUMULATIVE,
    INTENT_SET_VOLUME_RELATIVE: _CUMULATIVE,
    INTENT_MEDIA_SEARCH_AND_PLAY: ToolAnnotations(),
}


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return LLM tools for the integration's intents when its domain is exposed."""
    if api_id != LLM_API_ASSIST:
        return None

    if not llm_context.assistant:
        return None

    if not any(
        async_should_expose(hass, llm_context.assistant, state.entity_id)
        for state in hass.states.async_all(DOMAIN)
    ):
        return None

    tools: list[Tool] = [
        IntentTool(
            f"{DOMAIN}__{handler.intent_type}",
            handler,
            integration=DOMAIN,
            annotations=INTENT_ANNOTATIONS[handler.intent_type],
        )
        for handler in intent.async_get(hass)
        if handler.intent_type in LLM_INTENTS
    ]
    return LLMTools(tools=tools)
