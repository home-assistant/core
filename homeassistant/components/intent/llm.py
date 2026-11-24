"""LLM tools for the intent integration.

Exposes the generic, cross-domain intents owned by the intent integration
(device on/off, position, timers) as LLM tools. Domain-specific intents are
exposed by their own integration's ``llm.py`` platform.
"""

from typing import override

import probatio

from homeassistant.components.conversation import DOMAIN as CONVERSATION_DOMAIN
from homeassistant.components.homeassistant import async_should_expose
from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    floor_registry as fr,
    intent,
)
from homeassistant.helpers.llm import (
    LLM_API_ASSIST,
    IntentTool,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)

from .const import DOMAIN, TIMER_DATA
from .timers import TimerManager, async_device_supports_timers

# Generic intents exposed as LLM tools regardless of a timer-capable device.
LLM_INTENTS = {
    intent.INTENT_TURN_ON: "Turn on",
    intent.INTENT_TURN_OFF: "Turn off",
    intent.INTENT_CANCEL_ALL_TIMERS: "Cancel all timers",
    intent.INTENT_SET_POSITION: "Set position",
    intent.INTENT_STOP_MOVING: "Stop moving",
}

# Timer intents, only exposed for a device that supports timers.
TIMER_INTENTS = {
    intent.INTENT_START_TIMER: "Start timer",
    intent.INTENT_CANCEL_TIMER: "Cancel timer",
    intent.INTENT_INCREASE_TIMER: "Add time to timer",
    intent.INTENT_DECREASE_TIMER: "Remove time from timer",
    intent.INTENT_PAUSE_TIMER: "Pause timer",
    intent.INTENT_UNPAUSE_TIMER: "Resume timer",
    intent.INTENT_TIMER_STATUS: "Get timer status",
}

INTENT_TITLES = LLM_INTENTS | TIMER_INTENTS

# Every intent here acts on Home Assistant's own entities and timers, so none
# of them reaches an open world.
_CONTROL = ToolAnnotations(idempotent=True, open_world=False)
_REPEATS = ToolAnnotations(open_world=False)
_ADDS = ToolAnnotations(destructive=False, open_world=False)
_READ_ONLY = ToolAnnotations(read_only=True, open_world=False)

INTENT_ANNOTATIONS = {
    # Turning on a button entity presses it, which acts again on every call.
    intent.INTENT_TURN_ON: _REPEATS,
    intent.INTENT_TURN_OFF: _CONTROL,
    intent.INTENT_SET_POSITION: _CONTROL,
    intent.INTENT_STOP_MOVING: _CONTROL,
    intent.INTENT_CANCEL_ALL_TIMERS: _CONTROL,
    intent.INTENT_CANCEL_TIMER: _CONTROL,
    intent.INTENT_PAUSE_TIMER: _CONTROL,
    intent.INTENT_UNPAUSE_TIMER: _CONTROL,
    # A started timer can carry a command to run when it finishes, so it is
    # not only additive. Adding time to a timer is.
    intent.INTENT_START_TIMER: _REPEATS,
    intent.INTENT_INCREASE_TIMER: _ADDS,
    intent.INTENT_DECREASE_TIMER: _REPEATS,
    intent.INTENT_TIMER_STATUS: _READ_ONLY,
}


class ScheduleCommandTool(Tool):
    """LLM tool to run a command after a delay."""

    name = f"{DOMAIN}__schedule_command"
    title = "Schedule command"
    description = (
        "Run a command after a delay. When the delay ends, the command runs on "
        "its own, in a new conversation that has no access to this conversation. "
        "Before you call this tool, turn the user's request into a complete, "
        "standalone command. Replace references such as 'it', 'them', 'there' "
        "or 'as we discussed' with the exact devices, areas and values. "
        "Do not include the delay in the command."
    )
    annotations = _REPEATS
    integration = DOMAIN
    parameters = probatio.Schema(
        {
            probatio.Required(
                "command",
                description=(
                    "A standalone command, for example 'Turn off the kitchen "
                    "ceiling light'. It must make sense to someone who did not "
                    "see this conversation."
                ),
            ): probatio.All(str, probatio.Strip, probatio.NonEmpty()),
            probatio.Required(
                probatio.Any("hours", "minutes", "seconds")
            ): cv.positive_int,
        }
    )

    @override
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext
    ) -> ToolResult:
        """Start a timer that runs the command when it finishes."""
        data = self.parameters(tool_input.tool_args)
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        timer_manager.start_timer(
            llm_context.device_id,
            data.get("hours"),
            data.get("minutes"),
            data.get("seconds"),
            language=llm_context.language or hass.config.language,
            conversation_command=data["command"],
            conversation_agent_id=llm_context.agent_id,
            context=llm_context.context,
        )
        return ToolResult(data={"success": True})


DEVICE_CONTROL_TOOL_USAGE_PROMPT = (
    "When controlling Home Assistant always call the intent tools. "
    "Use intent__HassTurnOn to lock and intent__HassTurnOff to unlock a lock. "
    "When controlling a device, prefer passing just name and domain. "
    "When controlling an area, prefer passing just area name and domain."
)


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the generic intent tools and the device control prompt."""
    if api_id != LLM_API_ASSIST:
        return None

    supports_timers = (
        llm_context.device_id is not None
        and async_device_supports_timers(hass, llm_context.device_id)
    )
    wanted = set(LLM_INTENTS)
    if supports_timers:
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

    tools: list[Tool] = []
    for handler in handlers:
        tool = IntentTool(
            f"{DOMAIN}__{handler.intent_type}",
            handler,
            title=INTENT_TITLES[handler.intent_type],
            integration=DOMAIN,
            annotations=INTENT_ANNOTATIONS[handler.intent_type],
        )
        if handler.intent_type == intent.INTENT_START_TIMER:
            # Delayed commands go through the schedule command tool, which asks
            # the LLM for a standalone command.
            tool.parameters = probatio.Schema(
                {
                    key: value
                    for key, value in tool.parameters.schema.items()
                    if key != "conversation_command"
                }
            )
        tools.append(tool)

    # The command runs later on the same conversation agent, so a caller
    # without one (MCP, AI tasks) cannot schedule commands.
    can_schedule = (
        llm_context.assistant == CONVERSATION_DOMAIN
        and llm_context.agent_id is not None
    )
    if can_schedule:
        tools.append(ScheduleCommandTool())
    if not tools:
        return None

    # Only guide device control once something is exposed to control.
    if not exposed_domains:
        return LLMTools(tools=tools)

    # Tell the voice satellite which area it is in so generic commands target it.
    floor: fr.FloorEntry | None = None
    area: ar.AreaEntry | None = None
    if llm_context.device_id and (
        device := dr.async_get(hass).async_get(llm_context.device_id)
    ):
        area_reg = ar.async_get(hass)
        if (device_area_id := dr.async_get_effective_area_id(hass, device)) and (
            area := area_reg.async_get_area(device_area_id)
        ):
            if area.floor_id:
                floor = fr.async_get(hass).async_get_floor(area.floor_id)

    if area and floor:
        area_prompt = (
            f"You are in area {area.name} (floor {floor.name}) and all generic"
            " commands like 'turn on the lights' should target this area."
        )
    elif area:
        area_prompt = (
            f"You are in area {area.name} and all generic commands like"
            " 'turn on the lights' should target this area."
        )
    else:
        area_prompt = (
            "When a user asks to turn on all devices of a specific type, "
            "ask the user to specify an area, unless there is only one device"
            " of that type."
        )

    prompt_parts = [DEVICE_CONTROL_TOOL_USAGE_PROMPT, area_prompt]
    if not supports_timers:
        timer_prompt = "This device is not able to start timers."
        if can_schedule:
            timer_prompt += (
                f" It can still run a command later with {ScheduleCommandTool.name}."
            )
        prompt_parts.append(timer_prompt)
    return LLMTools(tools=tools, prompt="\n".join(prompt_parts))
