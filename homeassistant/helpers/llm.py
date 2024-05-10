"""Module to coordinate llm tools."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass
import inspect
import logging
from types import NoneType, UnionType
from typing import Any, get_args, get_type_hints

import voluptuous as vol

from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.hass_dict import HassKey

_LOGGER = logging.getLogger(__name__)

DATA_KEY: HassKey[dict[str, Tool]] = HassKey("llm_tool")


@dataclass(slots=True)
class ToolInput:
    """Tool input to be processed."""

    tool_name: str
    tool_args: dict[str, Any]
    platform: str
    context: Context | None
    user_prompt: str | None
    language: str | None
    agent_id: str | None
    conversation_id: str | None
    device_id: str | None
    assistant: str | None


class Tool:
    """LLM Tool base class."""

    name: str
    description: str | None = None
    parameters: vol.Schema = vol.Schema({})

    @abstractmethod
    async def async_call(self, hass: HomeAssistant, tool_input: ToolInput) -> Any:
        """Call the tool."""
        raise NotImplementedError

    def __repr__(self) -> str:
        """Represent a string of a Tool."""
        return f"<{self.__class__.__name__} - {self.name}>"


class FunctionTool(Tool):
    """LLM Tool representing an Python function.

    The function is recommended to have annotations for all parameters.
    If a parameter name is "hass" or any of the ToolInput attributes,
    then the value for that parameter will be provided by the conversation agent.
    All other arguments will be provided by the LLM.
    """

    function: Callable

    def __init__(
        self,
        function: Callable,
    ) -> None:
        """Init the class."""

        self.function = function

        self.name = function.__name__
        if self.name.startswith("async_"):
            self.name = self.name[len("async_") :]

        self.description = inspect.getdoc(function)

        schema = {}
        annotations = get_type_hints(function)
        for param in inspect.signature(function).parameters.values():
            if param.name == "hass":
                continue
            if hasattr(ToolInput, param.name):
                continue

            hint = annotations.get(param.name, str)
            if isinstance(hint, UnionType):
                hints = get_args(hint)
                if len(hints) == 2 and hints[0] is NoneType:
                    hint = vol.Maybe(hints[1])
                elif len(hints) == 2 and hints[1] is NoneType:
                    hint = vol.Maybe(hints[0])
                else:
                    hint = vol.Any(
                        *tuple(x if x is not NoneType else None for x in hints)
                    )

            schema[
                vol.Required(param.name)
                if param.default is inspect.Parameter.empty
                else vol.Optional(param.name, default=param.default)
            ] = hint

        self.parameters = vol.Schema(schema)

    async def async_call(self, hass: HomeAssistant, tool_input: ToolInput) -> Any:
        """Call the function."""
        kwargs = tool_input.tool_args
        for parameter in inspect.signature(self.function).parameters.values():
            if parameter.name == "hass":
                kwargs["hass"] = hass
            elif hasattr(ToolInput, parameter.name):
                kwargs[parameter.name] = getattr(tool_input, parameter.name)

        if inspect.iscoroutinefunction(self.function):
            return await self.function(**kwargs)
        return self.function(**kwargs)


@callback
def async_register_tool(hass: HomeAssistant, tool: Tool | Callable) -> None:
    """Register an LLM tool with Home Assistant."""
    if (tools := hass.data.get(DATA_KEY)) is None:
        tools = hass.data[DATA_KEY] = {}

    if not isinstance(tool, Tool):
        tool = FunctionTool(tool)

    if tool.name in tools:
        raise HomeAssistantError(f"Tool {tool.name} is already registered")

    tools[tool.name] = tool


@callback
def async_remove_tool(hass: HomeAssistant, tool: Tool | Callable | str) -> None:
    """Remove an LLM tool from Home Assistant."""
    if (tools := hass.data.get(DATA_KEY)) is None:
        return

    if isinstance(tool, str):
        tool_name = tool
    elif isinstance(tool, Tool):
        tool_name = tool.name
    else:
        tool_name = tool.__name__
        if tool_name.startswith("async_"):
            tool_name = tool_name[len("async_") :]

    tools.pop(tool_name, None)


@callback
def async_get_tools(hass: HomeAssistant) -> Iterable[Tool]:
    """Return a list of registered LLM tools."""
    tools: dict[str, Tool] = hass.data.get(DATA_KEY, {})

    return tools.values()


@callback
async def async_call_tool(hass: HomeAssistant, tool_input: ToolInput) -> Any:
    """Call a LLM tool, validate args and return the response."""
    try:
        tool = hass.data[DATA_KEY][tool_input.tool_name]
    except KeyError as err:
        raise HomeAssistantError(f'Tool "{tool_input.tool_name}" not found') from err

    if tool_input.context is None:
        tool_input.context = Context()

    tool_input.tool_args = tool.parameters(tool_input.tool_args)

    return await tool.async_call(hass, tool_input)


def llm_tool(hass: HomeAssistant) -> Callable:
    """Register a function as an LLM Tool with decorator."""

    def _llm_tool(func: Callable) -> Callable:
        async_register_tool(hass, func)
        return func

    return _llm_tool
