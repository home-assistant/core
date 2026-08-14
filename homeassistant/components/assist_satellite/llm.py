"""LLM tools for the assist_satellite integration."""

from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent
from homeassistant.helpers.llm import LLM_API_ASSIST, IntentTool, LLMContext, Tool


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the broadcast LLM tool."""
    if api_id != LLM_API_ASSIST:
        return None

    # assist_satellite registers the broadcast intent when it is set up, and
    # this platform is only queried once that has happened.
    tools: list[Tool] = [
        IntentTool(handler.intent_type, handler)
        for handler in intent.async_get(hass)
        if handler.intent_type == intent.INTENT_BROADCAST
    ]
    return LLMTools(tools=tools)
