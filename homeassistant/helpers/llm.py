"""Module to coordinate llm tools."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.climate.intent import INTENT_GET_TEMPERATURE
from homeassistant.components.weather.intent import INTENT_GET_WEATHER
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import JsonObjectType

from . import intent

_LOGGER = logging.getLogger(__name__)

IGNORE_INTENTS = [
    intent.INTENT_NEVERMIND,
    intent.INTENT_GET_STATE,
    INTENT_GET_WEATHER,
    INTENT_GET_TEMPERATURE,
]


@dataclass(slots=True)
class ToolInput:
    """Tool input to be processed."""

    tool_name: str
    tool_args: dict[str, Any]
    platform: str
    context: Context | None
    user_prompt: str | None
    language: str | None
    assistant: str | None


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


@callback
def async_get_tools(hass: HomeAssistant) -> Iterable[Tool]:
    """Return a list of LLM tools."""
    for intent_handler in intent.async_get(hass):
        if intent_handler.intent_type not in IGNORE_INTENTS:
            yield IntentTool(intent_handler)


@callback
async def async_call_tool(hass: HomeAssistant, tool_input: ToolInput) -> JsonObjectType:
    """Call a LLM tool, validate args and return the response."""
    for tool in async_get_tools(hass):
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
    )

    return await tool.async_call(hass, _tool_input)


class IntentTool(Tool):
    """LLM Tool representing an Intent."""

    def __init__(
        self,
        intent_handler: intent.IntentHandler,
    ) -> None:
        """Init the class."""
        self.name = intent_handler.intent_type
        self.description = f"Execute Home Assistant {self.name} intent"
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
        )
        return intent_response.as_dict()
