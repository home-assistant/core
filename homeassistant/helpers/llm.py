"""Module to coordinate llm tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

import voluptuous as vol

from homeassistant.components.climate.intent import INTENT_GET_TEMPERATURE
from homeassistant.components.conversation.trace import (
    ConversationTraceEventType,
    async_conversation_trace_append,
)
from homeassistant.components.weather.intent import INTENT_GET_WEATHER
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import JsonObjectType

from . import area_registry, device_registry, floor_registry, intent
from .singleton import singleton

LLM_API_ASSIST = "assist"


@callback
def async_render_no_api_prompt(hass: HomeAssistant) -> str:
    """Return the prompt to be used when no API is configured."""
    return (
        "Only if the user wants to control a device, tell them to edit the AI configuration "
        "and allow access to Home Assistant."
    )


@singleton("llm")
@callback
def _async_get_apis(hass: HomeAssistant) -> dict[str, API]:
    """Get all the LLM APIs."""
    return {
        LLM_API_ASSIST: AssistAPI(hass=hass),
    }


@callback
def async_register_api(hass: HomeAssistant, api: API) -> None:
    """Register an API to be exposed to LLMs."""
    apis = _async_get_apis(hass)

    if api.id in apis:
        raise HomeAssistantError(f"API {api.id} is already registered")

    apis[api.id] = api


@callback
def async_get_api(hass: HomeAssistant, api_id: str) -> API:
    """Get an API."""
    apis = _async_get_apis(hass)

    if api_id not in apis:
        raise HomeAssistantError(f"API {api_id} not found")

    return apis[api_id]


@callback
def async_get_apis(hass: HomeAssistant) -> list[API]:
    """Get all the LLM APIs."""
    return list(_async_get_apis(hass).values())


@dataclass(slots=True)
class ToolInput(ABC):
    """Tool input to be processed."""

    tool_name: str
    tool_args: dict[str, Any]
    platform: str
    context: Context | None
    user_prompt: str | None
    language: str | None
    assistant: str | None
    device_id: str | None


class Tool:
    """LLM Tool base class."""

    name: str
    description: str | None = None
    parameters: vol.Schema = vol.Schema({})

    @abstractmethod
    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput
    ) -> JsonObjectType:
        """Call the tool."""
        raise NotImplementedError

    def __repr__(self) -> str:
        """Represent a string of a Tool."""
        return f"<{self.__class__.__name__} - {self.name}>"


@dataclass(slots=True, kw_only=True)
class API(ABC):
    """An API to expose to LLMs."""

    hass: HomeAssistant
    id: str
    name: str

    @abstractmethod
    async def async_get_api_prompt(self, tool_input: ToolInput) -> str:
        """Return the prompt for the API."""
        raise NotImplementedError

    @abstractmethod
    @callback
    def async_get_tools(self) -> list[Tool]:
        """Return a list of tools."""
        raise NotImplementedError

    async def async_call_tool(self, tool_input: ToolInput) -> JsonObjectType:
        """Call a LLM tool, validate args and return the response."""
        async_conversation_trace_append(
            ConversationTraceEventType.LLM_TOOL_CALL, asdict(tool_input)
        )

        for tool in self.async_get_tools():
            if tool.name == tool_input.tool_name:
                break
        else:
            raise HomeAssistantError(f'Tool "{tool_input.tool_name}" not found')

        _tool_input = ToolInput(
            tool_name=tool.name,
            tool_args=tool.parameters(tool_input.tool_args),
            platform=tool_input.platform,
            context=tool_input.context or Context(),
            user_prompt=tool_input.user_prompt,
            language=tool_input.language,
            assistant=tool_input.assistant,
            device_id=tool_input.device_id,
        )

        return await tool.async_call(self.hass, _tool_input)


class IntentTool(Tool):
    """LLM Tool representing an Intent."""

    def __init__(
        self,
        intent_handler: intent.IntentHandler,
    ) -> None:
        """Init the class."""
        self.name = intent_handler.intent_type
        self.description = (
            intent_handler.description or f"Execute Home Assistant {self.name} intent"
        )
        if slot_schema := intent_handler.slot_schema:
            self.parameters = vol.Schema(slot_schema)

    async def async_call(
        self, hass: HomeAssistant, tool_input: ToolInput
    ) -> JsonObjectType:
        """Handle the intent."""
        slots = {key: {"value": val} for key, val in tool_input.tool_args.items()}

        intent_response = await intent.async_handle(
            hass,
            tool_input.platform,
            self.name,
            slots,
            tool_input.user_prompt,
            tool_input.context,
            tool_input.language,
            tool_input.assistant,
            tool_input.device_id,
        )
        return intent_response.as_dict()


class AssistAPI(API):
    """API exposing Assist API to LLMs."""

    IGNORE_INTENTS = {
        intent.INTENT_NEVERMIND,
        intent.INTENT_GET_STATE,
        INTENT_GET_WEATHER,
        INTENT_GET_TEMPERATURE,
    }

    def __init__(self, hass: HomeAssistant) -> None:
        """Init the class."""
        super().__init__(
            hass=hass,
            id=LLM_API_ASSIST,
            name="Assist",
        )

    async def async_get_api_prompt(self, tool_input: ToolInput) -> str:
        """Return the prompt for the API."""
        prompt = (
            "Call the intent tools to control Home Assistant. "
            "Just pass the name to the intent."
        )
        if tool_input.device_id:
            device_reg = device_registry.async_get(self.hass)
            device = device_reg.async_get(tool_input.device_id)
            if device:
                area_reg = area_registry.async_get(self.hass)
                if device.area_id and (area := area_reg.async_get_area(device.area_id)):
                    floor_reg = floor_registry.async_get(self.hass)
                    if area.floor_id and (
                        floor := floor_reg.async_get_floor(area.floor_id)
                    ):
                        prompt += f" You are in {area.name} ({floor.name})."
                    else:
                        prompt += f" You are in {area.name}."
        if tool_input.context and tool_input.context.user_id:
            user = await self.hass.auth.async_get_user(tool_input.context.user_id)
            if user:
                prompt += f" The user name is {user.name}."
        return prompt

    @callback
    def async_get_tools(self) -> list[Tool]:
        """Return a list of LLM tools."""
        return [
            IntentTool(intent_handler)
            for intent_handler in intent.async_get(self.hass)
            if intent_handler.intent_type not in self.IGNORE_INTENTS
        ]
