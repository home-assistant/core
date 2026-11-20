"""Code mode: expose the tools of an LLM API as functions for sandboxed code."""

import asyncio
import builtins
from collections.abc import Callable, Coroutine
from contextlib import AsyncExitStack
from datetime import date, time, timedelta
from functools import partial
import json
import keyword
import re
from typing import Any, override

import probatio
from pydantic_monty import AsyncMonty, CollectString, MontyError, ResourceLimits

from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import chat_session, config_validation as cv
from homeassistant.helpers.llm import (
    APIInstance,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import JsonObjectType, JsonValueType

from .const import DOMAIN

# The sandbox clock stops while a tool call runs, so the wall clock has its own limit.
TIMEOUT = 60
LIMITS = ResourceLimits(
    max_feed_duration_secs=10,
    max_memory=64 * 1024 * 1024,
    max_suspensions=200,
)
MAX_OUTPUT_BYTES = 64 * 1024
# Code can raise an error with a message of any size.
MAX_ERROR_SIZE = 4096
# Limit for the result of the code, in values plus characters.
MAX_RESULT_SIZE = 64 * 1024
# The JSON encoder of Home Assistant fails on deeper values.
MAX_RESULT_DEPTH = 100
# The JSON encoder of Home Assistant fails on integers outside this range.
MIN_JSON_INT = -(2**63)
MAX_JSON_INT = 2**64 - 1
# Types whose string has a size close to the size of the value.
_SCALAR_TYPES = (bool, int, float, type, date, time, timedelta)
SEARCH_LIMIT = 10
# Modules that the code can use without an import.
IMPORTED_MODULES = ("asyncio", "datetime", "json", "math", "re")
# Dicts in a parameter type are written with their keys up to this depth.
MAX_TYPE_DEPTH = 3
# Sandbox processes for all chat sessions. A run waits when all are in use.
MAX_SANDBOXES = 10


class Sandboxes:
    """The pool of sandbox processes and the chat sessions that keep it running."""

    def __init__(self) -> None:
        """Init the class."""
        self.lock = asyncio.Lock()
        self.pool: AsyncMonty | None = None
        self.conversation_ids: set[str] = set()
        self.async_stop: CALLBACK_TYPE | None = None


DATA_SANDBOXES: HassKey[Sandboxes] = HassKey("llm_code_mode_sandboxes")

PROMPT = (
    "The tools of this API are Python functions. "
    "You cannot call them directly: write Python code that calls them and run "
    "it with the `execute` tool.\n"
    "- Find functions with the `search` tool. It returns their declarations. "
    "Do not guess the name or the parameters of a function.\n"
    "- Every function is async and takes keyword arguments: "
    "`result = await name(param=value)`. The result is a dict.\n"
    '- A parameter type like `{"key": str, "other"?: int}` is a dict with '
    "those keys. A key with `?` is optional.\n"
    "- The modules `asyncio`, `datetime`, `json`, `math` and `re` are already "
    "imported. Do not import them.\n"
    "- Run independent calls in parallel with `asyncio.gather`.\n"
    "- `execute` returns the value of the last expression and the printed "
    "output. Return only the data that you need.\n"
    "- The code cannot access files or the network, and most other modules "
    "do not exist.\n"
)

_JSON_TYPES = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "object": "dict",
    "null": "None",
}


@callback
def async_create_api_instance(
    api_instance: APIInstance, conversation_id: str
) -> APIInstance:
    """Return an API instance with a search tool and an execute tool.

    The sandboxes that run the code stop when the chat session of the
    conversation is cleaned up.
    """
    hass = api_instance.api.hass
    sandboxes = hass.data.setdefault(DATA_SANDBOXES, Sandboxes())
    if conversation_id not in sandboxes.conversation_ids:
        sandboxes.conversation_ids.add(conversation_id)
        with chat_session.async_get_chat_session(
            hass, conversation_id, context=None
        ) as session:
            session.async_on_cleanup(
                partial(_async_release_pool, hass, conversation_id)
            )

    functions: list[ToolFunction] = []
    names: set[str] = set()
    for tool in api_instance.tools:
        base = re.sub(r"\W", "_", tool.name)
        # A name of a builtin or of an imported module would hide the function.
        if (
            not base.isidentifier()
            or keyword.iskeyword(base)
            or hasattr(builtins, base)
            or base in IMPORTED_MODULES
        ):
            base = f"tool_{base}"
        # Different tool names can give the same Python name.
        name = base
        suffix = 1
        while name in names:
            suffix += 1
            name = f"{base}_{suffix}"
        names.add(name)
        functions.append(ToolFunction(api_instance, tool, name))
    return APIInstance(
        api=api_instance.api,
        api_prompt=f"{api_instance.api_prompt}\n{PROMPT}",
        llm_context=api_instance.llm_context,
        tools=[SearchTool(functions), ExecuteTool(api_instance, functions)],
        custom_serializer=api_instance.custom_serializer,
    )


class ToolError(Exception):
    """Error that a failed tool call raises in the code.

    The sandbox does not have the error classes of Home Assistant. The code
    gets an Exception with the message of this error.
    """


class ToolFunction:
    """A tool as a function that code can call."""

    def __init__(self, api_instance: APIInstance, tool: Tool, name: str) -> None:
        """Init the class."""
        self._api_instance = api_instance
        self._tool_name = tool.name
        self.name = name
        self.description = tool.description or ""
        schema = probatio.to_openapi(
            tool.parameters,
            custom_serializer=api_instance.custom_serializer,
            openapi_version="3.1.0",
        )
        properties: dict[str, Any] = schema.get("properties", {})
        required = set(schema.get("required", []))
        self.parameters = list(properties)
        lines = [f"async def {self.name}("]
        for param, prop in sorted(
            properties.items(), key=lambda item: item[0] not in required
        ):
            default = "" if param in required else " = None"
            comment = (
                f"  # {' '.join(description.split())}"
                if (description := prop.get("description"))
                else ""
            )
            lines.append(f"    {param}: {_python_type(prop)}{default},{comment}")
        signature = (
            "\n".join([lines[0], "    *,", *lines[1:], ") -> dict:"])
            if properties
            else f"{lines[0]}) -> dict:"
        )
        docstring = f'    """{" ".join(self.description.split())}"""'
        self.declaration = f"{signature}\n{docstring}"

    def create(
        self, tasks: set[asyncio.Task[Any]]
    ) -> Callable[..., Coroutine[Any, Any, JsonObjectType]]:
        """Return the sandbox function, which records its running calls in tasks."""

        async def call_tool(**kwargs: Any) -> JsonObjectType:
            task = asyncio.current_task()
            assert task is not None
            tasks.add(task)
            try:
                # The arguments can contain the same list many times, like
                # the result of the code.
                tool_args = _json_value(kwargs, [MAX_RESULT_SIZE], MAX_RESULT_DEPTH)
                assert isinstance(tool_args, dict)
                result = await self._api_instance.async_call_tool(
                    ToolInput(tool_name=self._tool_name, tool_args=tool_args)
                )
            except ValueError as err:
                raise ToolError(
                    "The arguments are too large or nested too deep"
                ) from err
            except (HomeAssistantError, probatio.Invalid) as err:
                raise ToolError(f"{type(err).__name__}: {err}") from err
            finally:
                tasks.discard(task)
            if result.error:
                raise ToolError(json.dumps(result.data))
            return result.data

        return call_tool


def _python_type(schema: dict[str, Any], depth: int = MAX_TYPE_DEPTH) -> str:
    """Return the Python type hint for a JSON schema.

    A dict with known keys is written as `{"key": type, "optional_key"?: type}`.
    """
    if "enum" in schema:
        return f"Literal[{', '.join(repr(value) for value in schema['enum'])}]"
    if variants := schema.get("anyOf") or schema.get("oneOf"):
        return " | ".join(
            dict.fromkeys(_python_type(variant, depth) for variant in variants)
        )
    json_type = schema.get("type")
    if isinstance(json_type, list):
        return " | ".join(
            _python_type({**schema, "type": item}, depth) for item in json_type
        )
    if json_type == "array":
        return f"list[{_python_type(schema.get('items', {}), depth)}]"
    if json_type == "object" and depth and (properties := schema.get("properties")):
        required = set(schema.get("required", []))
        keys = ", ".join(
            f"{json.dumps(key)}{'' if key in required else '?'}: "
            f"{_python_type(prop, depth - 1)}"
            for key, prop in properties.items()
        )
        return f"{{{keys}}}"
    return _JSON_TYPES.get(str(json_type), "Any")


async def _async_get_pool(hass: HomeAssistant) -> AsyncMonty:
    """Return the pool of sandbox processes, and start it when it does not run."""
    sandboxes = hass.data[DATA_SANDBOXES]
    async with sandboxes.lock:
        if sandboxes.pool is not None:
            return sandboxes.pool
        stack = AsyncExitStack()
        pool = await stack.enter_async_context(
            AsyncMonty(min_processes=0, max_processes=MAX_SANDBOXES)
        )

        async def _async_stop_on_close(_: Event) -> None:
            sandboxes.pool = sandboxes.async_stop = None
            await stack.aclose()

        unsub = hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_CLOSE, _async_stop_on_close
        )

        @callback
        def _async_stop() -> None:
            unsub()
            hass.async_create_task(stack.aclose(), "code_mode_stop_sandboxes")

        sandboxes.pool = pool
        sandboxes.async_stop = _async_stop
        return pool


@callback
def _async_release_pool(hass: HomeAssistant, conversation_id: str) -> None:
    """Remove a chat session, and stop the sandbox pool after the last one."""
    sandboxes = hass.data[DATA_SANDBOXES]
    sandboxes.conversation_ids.discard(conversation_id)
    if not sandboxes.conversation_ids and sandboxes.async_stop is not None:
        sandboxes.async_stop()
        sandboxes.pool = sandboxes.async_stop = None


class SearchTool(Tool):
    """Tool that finds the functions that code can call."""

    name = "search"
    title = "Search functions"
    description = (
        "Find functions to call from the code of the `execute` tool. "
        "Returns the Python declaration of each function that matches."
    )
    parameters = probatio.Schema(
        {
            probatio.Required(
                "query", description="Function names or words that describe the task"
            ): cv.string
        }
    )
    annotations = ToolAnnotations(read_only=True, open_world=False)
    integration = DOMAIN

    def __init__(self, functions: list[ToolFunction]) -> None:
        """Init the class."""
        self._functions = functions

    @override
    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: ToolInput,
        llm_context: LLMContext,
    ) -> ToolResult:
        """Return the functions that match the query best."""
        words = set(_words(self.parameters(tool_input.tool_args)["query"]))
        scored = []
        for function in self._functions:
            name_words = set(_words(function.name))
            other_words = set(
                _words(f"{function.description} {' '.join(function.parameters)}")
            )
            # A word in the name says more than a word in the description.
            if score := 3 * len(words & name_words) + len(words & other_words):
                scored.append((score, function))
        scored.sort(key=lambda item: item[0], reverse=True)
        return ToolResult(
            data={
                "functions": [
                    function.declaration for _, function in scored[:SEARCH_LIMIT]
                ]
            }
        )


def _words(text: str) -> list[str]:
    """Split text into lower case words, also at camel case and underscores."""
    return [
        word.lower() for word in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", text)
    ]


class ExecuteTool(Tool):
    """Tool that runs code that calls the functions."""

    name = "execute"
    title = "Execute code"
    description = (
        "Run Python code in a sandbox. The code calls the functions of this API. "
        "Returns the value of the last expression and the printed output."
    )
    parameters = probatio.Schema(
        {probatio.Required("code", description="Python source code"): cv.string}
    )
    integration = DOMAIN

    def __init__(
        self, api_instance: APIInstance, functions: list[ToolFunction]
    ) -> None:
        """Init the class."""
        self._api_instance = api_instance
        self._functions = functions

    @override
    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: ToolInput,
        llm_context: LLMContext,
    ) -> ToolResult:
        """Run the code in a sandbox."""
        code = self.parameters(tool_input.tool_args)["code"]
        # The chat log keeps this tool between turns, so the tools must get
        # the context of the current turn.
        self._api_instance.llm_context = llm_context
        try:
            return await self._async_run(await _async_get_pool(hass), code)
        except (MontyError, OSError) as err:
            return ToolResult(
                data={"error": str(err)[:MAX_ERROR_SIZE], "output": ""}, error=True
            )

    async def _async_run(self, pool: AsyncMonty, code: str) -> ToolResult:
        """Run the code in a sandbox of the pool."""
        tasks: set[asyncio.Task[Any]] = set()
        output = CollectString(MAX_OUTPUT_BYTES)
        try:
            async with (
                asyncio.timeout(TIMEOUT),
                pool.checkout(limits=LIMITS) as session,
            ):
                await session.feed_run(f"import {', '.join(IMPORTED_MODULES)}")
                result = await session.feed_run(
                    code,
                    external_lookup={
                        function.name: function.create(tasks)
                        for function in self._functions
                    },
                    print_callback=output,
                )
        except (MontyError, TimeoutError) as err:
            return ToolResult(
                data={
                    "error": str(err)[:MAX_ERROR_SIZE] or "Timeout",
                    "output": output.output,
                },
                error=True,
            )
        finally:
            # The sandbox does not stop tool calls that run when the code ends.
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        try:
            json_result = _json_value(result, [MAX_RESULT_SIZE], MAX_RESULT_DEPTH)
        except ValueError:
            return ToolResult(
                data={
                    "error": "The result is too large or nested too deep. "
                    "Return less data.",
                    "output": output.output,
                },
                error=True,
            )
        return ToolResult(data={"result": json_result, "output": output.output})


def _json_value(value: Any, budget: list[int], depth: int) -> JsonValueType:
    """Return the sandbox result as a JSON value.

    The sandbox can return values that JSON cannot represent, such as sets
    and dicts with tuple keys. A small result can also contain the same list
    many times, so the budget limits the size of the converted value.
    """
    budget[0] -= 1 + (len(value) if isinstance(value, str) else 0)
    if budget[0] < 0 or depth < 0:
        raise ValueError("Result too large")
    if isinstance(value, int) and not MIN_JSON_INT <= value <= MAX_JSON_INT:
        return _json_text(value, budget, depth)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {
            _json_text(key, budget, depth): _json_value(item, budget, depth - 1)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item, budget, depth - 1) for item in value]
    return _json_text(value, budget, depth)


def _json_text(value: Any, budget: list[int], depth: int) -> str:
    """Return a dict key, or a value without a JSON type, as a string.

    The string of a value can be much larger than the value, so the size is
    checked before the conversion where that is possible.
    """
    if isinstance(value, str):
        text = value
    elif isinstance(value, (tuple, frozenset)):
        # The conversion of the items applies the budget.
        text = str(_json_value(value, budget, depth))
    elif isinstance(value, bytes):
        if len(value) > budget[0]:
            raise ValueError("Result too large")
        text = str(value)
    elif value is None or isinstance(value, _SCALAR_TYPES):
        text = str(value)
    else:
        text = f"<{type(value).__name__}>"
    budget[0] -= len(text)
    if budget[0] < 0:
        raise ValueError("Result too large")
    return text
