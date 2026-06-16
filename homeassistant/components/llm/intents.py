"""LLM tools wrapping exposed intents."""

from functools import cache, partial

import slugify as unicode_slug

from homeassistant.components.cover import INTENT_CLOSE_COVER, INTENT_OPEN_COVER
from homeassistant.components.intent import async_device_supports_timers
from homeassistant.components.weather import INTENT_GET_WEATHER
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import intent, llm

DEVICE_CONTROL_TOOL_USAGE_PROMPT = (
    "When controlling Home Assistant always call the intent tools. "
    "Use HassTurnOn to lock and HassTurnOff to unlock a lock. "
    "When controlling a device, prefer passing just name and domain. "
    "When controlling an area, prefer passing just area name and domain."
)

IGNORE_INTENTS = {
    intent.INTENT_GET_TEMPERATURE,
    INTENT_GET_WEATHER,
    INTENT_OPEN_COVER,  # deprecated
    INTENT_CLOSE_COVER,  # deprecated
    intent.INTENT_GET_STATE,
    intent.INTENT_NEVERMIND,
    intent.INTENT_TOGGLE,
    intent.INTENT_GET_CURRENT_DATE,
    intent.INTENT_GET_CURRENT_TIME,
    intent.INTENT_RESPOND,
}

TIMER_INTENTS = {
    intent.INTENT_START_TIMER,
    intent.INTENT_CANCEL_TIMER,
    intent.INTENT_INCREASE_TIMER,
    intent.INTENT_DECREASE_TIMER,
    intent.INTENT_PAUSE_TIMER,
    intent.INTENT_UNPAUSE_TIMER,
    intent.INTENT_TIMER_STATUS,
}

_slugify = cache(partial(unicode_slug.slugify, separator="_", lowercase=False))


@callback
def intent_tools(hass: HomeAssistant, llm_context: llm.LLMContext) -> llm.LLMTools:
    """Return the intent tools and their prompt for the exposed entities."""
    exposed = (
        llm.async_get_exposed_entities(hass, llm_context.assistant, include_state=False)
        if llm_context.assistant
        else None
    )

    ignore = IGNORE_INTENTS
    if not llm_context.device_id or not async_device_supports_timers(
        hass, llm_context.device_id
    ):
        ignore = ignore | TIMER_INTENTS

    handlers = [
        handler
        for handler in intent.async_get(hass)
        if handler.intent_type not in ignore
    ]

    if exposed is not None:
        exposed_domains = {info["domain"] for info in exposed["entities"].values()}
        handlers = [
            handler
            for handler in handlers
            if handler.platforms is None or handler.platforms & exposed_domains
        ]

    tools: list[llm.Tool] = [
        llm.IntentTool(_slugify(handler.intent_type), handler) for handler in handlers
    ]

    prompt = None
    if exposed and exposed["entities"]:
        parts = [DEVICE_CONTROL_TOOL_USAGE_PROMPT]
        if not llm_context.device_id or not async_device_supports_timers(
            hass, llm_context.device_id
        ):
            parts.append("This device is not able to start timers.")
        prompt = "\n".join(parts)

    return llm.LLMTools(tools=tools, prompt=prompt)
