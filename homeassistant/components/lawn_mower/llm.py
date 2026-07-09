"""LLM tools for the lawn_mower integration."""

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent
from homeassistant.helpers.llm import LLM_API_ASSIST, IntentTool, LLMContext, Tool

from .const import DOMAIN
from .intent import INTENT_LANW_MOWER_DOCK, INTENT_LANW_MOWER_START_MOWING

# Intents owned by this integration that are exposed as LLM tools.
LLM_INTENTS = (INTENT_LANW_MOWER_DOCK, INTENT_LANW_MOWER_START_MOWING)


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
        IntentTool(handler.intent_type, handler)
        for handler in intent.async_get(hass)
        if handler.intent_type in LLM_INTENTS
    ]
    return LLMTools(tools=tools)
