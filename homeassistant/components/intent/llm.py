"""LLM tools for the intent integration.

Exposes the generic, cross-domain intents owned by the intent integration
(device on/off, position, timers) as LLM tools. Domain-specific intents are
exposed by their own integration's ``llm.py`` platform.
"""

from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    floor_registry as fr,
    intent,
)
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

DEVICE_CONTROL_TOOL_USAGE_PROMPT = (
    "When controlling Home Assistant always call the intent tools. "
    "Use HassTurnOn to lock and HassTurnOff to unlock a lock. "
    "When controlling a device, prefer passing just name and domain. "
    "When controlling an area, prefer passing just area name and domain."
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

    # Only guide device control once something is exposed to control.
    prompt = _async_get_prompt(hass, llm_context) if exposed_domains else None
    return LLMTools(tools=tools, prompt=prompt)


@callback
def _async_get_prompt(hass: HomeAssistant, llm_context: LLMContext) -> str:
    """Return the device control prompt for the exposed intent tools."""
    prompt_parts = [
        DEVICE_CONTROL_TOOL_USAGE_PROMPT,
        _async_get_area_prompt(hass, llm_context),
    ]
    if no_timer_prompt := _async_get_no_timer_prompt(hass, llm_context):
        prompt_parts.append(no_timer_prompt)
    return "\n".join(prompt_parts)


@callback
def _async_get_no_timer_prompt(
    hass: HomeAssistant, llm_context: LLMContext
) -> str | None:
    """Return a prompt when the device cannot start timers."""
    if not llm_context.device_id or not async_device_supports_timers(
        hass, llm_context.device_id
    ):
        return "This device is not able to start timers."
    return None


@callback
def _async_get_area_prompt(hass: HomeAssistant, llm_context: LLMContext) -> str:
    """Return the area prompt for the voice satellite."""
    floor: fr.FloorEntry | None = None
    area: ar.AreaEntry | None = None
    extra = ""
    if llm_context.device_id:
        device_reg = dr.async_get(hass)
        device = device_reg.async_get(llm_context.device_id)

        if device:
            area_reg = ar.async_get(hass)
            if device.area_id and (area := area_reg.async_get_area(device.area_id)):
                floor_reg = fr.async_get(hass)
                if area.floor_id:
                    floor = floor_reg.async_get_floor(area.floor_id)

        extra = (
            "and all generic commands like"
            " 'turn on the lights' should target"
            " this area."
        )

    if floor and area:
        return f"You are in area {area.name} (floor {floor.name}) {extra}".strip()
    if area:
        return f"You are in area {area.name} {extra}".strip()
    return (
        "When a user asks to turn on all devices of a specific type, "
        "ask the user to specify an area, unless there"
        " is only one device of that type."
    )
