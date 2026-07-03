"""LLM tools for the media_player integration."""

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent
from homeassistant.helpers.llm import IntentTool, LLMContext, Tool

from .const import DOMAIN

# Intents owned by this integration that are exposed as LLM tools.
LLM_INTENTS = (
    "HassMediaNext",
    "HassMediaPause",
    "HassMediaPlayerMute",
    "HassMediaPlayerUnmute",
    "HassMediaPrevious",
    "HassMediaSearchAndPlay",
    "HassMediaUnpause",
    "HassSetVolume",
    "HassSetVolumeRelative",
)


@callback
def async_get_tools(hass: HomeAssistant, llm_context: LLMContext) -> LLMTools:
    """Return LLM tools for the integration's intents when its domain is exposed."""
    if not llm_context.assistant:
        return LLMTools(tools=[])

    if not any(
        async_should_expose(hass, llm_context.assistant, state.entity_id)
        for state in hass.states.async_all(DOMAIN)
    ):
        return LLMTools(tools=[])

    tools: list[Tool] = [
        IntentTool(handler.intent_type, handler)
        for handler in intent.async_get(hass)
        if handler.intent_type in LLM_INTENTS
    ]
    return LLMTools(tools=tools)
