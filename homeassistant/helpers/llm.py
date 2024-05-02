"""Module to coordinate llm tools."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import cached_property
import inspect
import logging
from types import FunctionType, NoneType, UnionType
from typing import Any, get_args, get_type_hints

import voluptuous as vol
from voluptuous_openapi import UNSUPPORTED, convert

from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from . import area_registry as ar, config_validation as cv, floor_registry as fr, intent

_LOGGER = logging.getLogger(__name__)

DATA_KEY = "llm_tool"


def default_custom_serializer(schema: Any) -> Any:
    """Serialize additional types in OpenAPI-compatible format."""
    from homeassistant.util.color import (  # pylint: disable=import-outside-toplevel
        color_name_to_rgb,
    )

    if schema is cv.string:
        return {"type": "string"}

    if schema is cv.boolean:
        return {"type": "boolean"}

    if schema is color_name_to_rgb:
        return {"type": "string"}

    if isinstance(schema, cv.multi_select):
        return {"enum": schema.options}

    if isinstance(schema, FunctionType):
        return {}

    return UNSUPPORTED


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
    description: str | None
    parameters: vol.Schema
    custom_serializer: Callable[[Any], Any]

    def __init__(
        self,
        name: str,
        description: str | None,
        parameters: vol.Schema = vol.Schema({}),
        custom_serializer: Callable[[Any], Any] = default_custom_serializer,
    ) -> None:
        """Init the class."""
        self.name = name
        self.description = description
        self.parameters = parameters
        self.custom_serializer = custom_serializer

    @cached_property
    def specification(self) -> dict[str, Any]:
        """Get the tool specification in OpenAPI-compatible format."""
        result = {"name": self.name}
        if self.description:
            result["description"] = self.description
        result["parameters"] = convert(
            self.parameters, custom_serializer=self.custom_serializer
        )
        return result

    @abstractmethod
    async def async_call(self, hass: HomeAssistant, tool_input: ToolInput) -> Any:
        """Call the tool."""
        raise NotImplementedError

    def as_dict(self) -> dict[str, Any]:
        """Get the tool specification in OpenAPI-compatible format."""
        return self.specification

    def __repr__(self) -> str:
        """Represent a string of a Tool."""
        return f"<{self.__class__.__name__} - {self.name}>"


class IntentTool(Tool):
    """LLM Tool representing an Intent."""

    def __init__(
        self,
        intent_type: str,
        slot_schema: vol.Schema | None = None,
    ) -> None:
        """Init the class."""
        if slot_schema is None:
            slot_schema = vol.Schema({})
        else:
            slot_schema = vol.Schema(
                {key: val.schema["value"] for key, val in slot_schema.schema.items()}
            )

        super().__init__(
            intent_type,
            f"Execute Home Assistant {intent_type} intent",
            slot_schema,
        )

    async def async_call(self, hass: HomeAssistant, tool_input: ToolInput) -> Any:
        """Handle the intent."""
        slots = {key: {"value": val} for key, val in tool_input.tool_args.items()}

        if "area" in slots:
            areas = ar.async_get(hass)
            id_or_name = slots["area"]["value"]

            area = areas.async_get_area(id_or_name) or areas.async_get_area_by_name(
                id_or_name
            )
            if not area:
                # Check area aliases
                for maybe_area in areas.areas.values():
                    if not maybe_area.aliases:
                        continue

                    for area_alias in maybe_area.aliases:
                        if id_or_name == area_alias.casefold():
                            area = maybe_area
                            break
            if area:
                slots["area"]["value"] = area.id
                slots["area"]["text"] = area.name
            else:
                slots["area"]["text"] = id_or_name

        if "floor" in slots:
            floors = fr.async_get(hass)
            id_or_name = slots["floor"]["value"]

            floor = floors.async_get_floor(
                id_or_name
            ) or floors.async_get_floor_by_name(id_or_name)
            if not floor:
                # Check floor aliases
                for maybe_floor in floors.floors.values():
                    if not maybe_floor.aliases:
                        continue

                    for floor_alias in maybe_floor.aliases:
                        if id_or_name == floor_alias.casefold():
                            floor = maybe_floor
                            break
            if floor:
                slots["floor"]["value"] = floor.floor_id
                slots["floor"]["text"] = floor.name
            else:
                slots["floor"]["text"] = id_or_name

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


class FunctionTool(Tool):
    """LLM Tool representing an Python function.

    The function is recommended to have annotations for all parameters.
    If a parameter name is "hass", "tool_input", or any of the ToolInput attributes,
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

        name = function.__name__
        if name.startswith("async_"):
            name = name[len("async_") :]

        description = inspect.getdoc(function)

        schema = {}
        annotations = get_type_hints(function)
        for param in inspect.signature(function).parameters.values():
            if param.name == "hass":
                continue
            if param.name == "tool_input":
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

        super().__init__(
            name,
            description,
            vol.Schema(schema),
        )

    async def async_call(self, hass: HomeAssistant, tool_input: ToolInput) -> Any:
        """Call the function."""
        kwargs = tool_input.tool_args
        for parameter in inspect.signature(self.function).parameters.values():
            if parameter.name == "hass":
                kwargs["hass"] = hass
            elif parameter.name == "tool_input":
                kwargs["tool_input"] = tool_input
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
    if (tools := hass.data.get(DATA_KEY)) is None:
        tools = {}

    return tools.values()


@callback
async def async_call_tool(hass: HomeAssistant, tool_input: ToolInput) -> Any:
    """Call a LLM tool, validate args and return the response."""
    if (tools := hass.data.get(DATA_KEY)) is None:
        tools = {}

    tool = tools[tool_input.tool_name]

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
