"""LLM tools for the intent integration.

Exposes the generic, cross-domain intents owned by the intent integration
(device on/off, position, timers) as LLM tools. Domain-specific intents are
exposed by their own integration's ``llm.py`` platform.
"""

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent
from homeassistant.helpers.llm import LLM_API_ASSIST, IntentTool, LLMContext, Tool

from .timers import async_device_supports_timers

# Generic intents exposed as LLM tools regardless of a timer-capable device.
LLM_INTENTS = (
    intent.INTENT_TURN_ON,
    intent.INTENT_TURN_OFF,
    intent.INTENT_CANCEL_ALL_TIMERS,
    intent.INTENT_SET_POSITION,
    intent.INTENT_STOP_MOVING,
)

# Timer intents, only exposed for a device that supports timers.
TIMER_INTENTS = (
    intent.INTENT_START_TIMER,
    intent.INTENT_CANCEL_TIMER,
    intent.INTENT_INCREASE_TIMER,
    intent.INTENT_DECREASE_TIMER,
    intent.INTENT_PAUSE_TIMER,
    intent.INTENT_UNPAUSE_TIMER,
    intent.INTENT_TIMER_STATUS,
)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return LLM tools for the generic intents."""
    if api_id != LLM_API_ASSIST:
        return None

    wanted = set(LLM_INTENTS)
    if llm_context.device_id and async_device_supports_timers(
        hass, llm_context.device_id
    ):
        wanted.update(TIMER_INTENTS)

    exposed_domains = {
        state.domain
        for state in hass.states.async_all()
        if async_should_expose(hass, llm_context.assistant, state.entity_id)
    }
    handlers = [
        handler
        for handler in intent.async_get(hass)
        if handler.intent_type in wanted
        and (handler.platforms is None or handler.platforms & exposed_domains)
    ]

    tools: list[Tool] = [
        IntentTool(handler.intent_type, handler) for handler in handlers
    ]
    if not tools:
        return None
    return LLMTools(tools=tools)
