"""LLM API that replaces the tools of other APIs with code execution."""

import asyncio
from collections.abc import Callable, Coroutine
import json
import re
from typing import Any, override

import probatio
from pydantic_monty import AsyncMonty, CollectString, MontyError, ResourceLimits

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.llm import (
    APIInstance,
    APIWrapper,
    LLMContext,
    Tool,
    ToolAnnotations,
    ToolInput,
    ToolResult,
)
from homeassistant.util.json import JsonObjectType

from .const import DOMAIN

# The sandbox clock stops while a tool call runs, so the wall clock has its own limit.
TIMEOUT = 60
LIMITS = ResourceLimits(
    max_feed_duration_secs=10,
    max_memory=64 * 1024 * 1024,
    max_suspensions=200,
)
MAX_OUTPUT_BYTES = 64 * 1024
# Function declarations are part of the prompt up to this size, in characters.
INLINE_BUDGET = 8000
SEARCH_LIMIT = 10

PROMPT = (
    "The tools of this API are Python functions. "
    "You cannot call them directly: write Python code that calls them and run "
    "it with the `execute` tool.\n"
    "- Every function is async and takes keyword arguments: "
    "`result = await name(param=value)`. The result is a dict.\n"
    "- Run independent calls in parallel with `asyncio.gather`.\n"
    "- `execute` returns the value of the last expression and the printed "
    "output. Return only the data that you need.\n"
    "- The code cannot import other modules or access files or the network.\n"
)

_JSON_TYPES = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "object": "dict",
    "null": "None",
}


class CodeModeAPI(APIWrapper):
    """API that exposes the tools of the other selected APIs as code."""

    def __init__(self, hass: HomeAssistant, pool: AsyncMonty) -> None:
        """Init the class."""
        super().__init__(hass=hass, id=DOMAIN, name="Code mode")
        self._pool = pool

    @override
    async def async_wrap_api_instance(self, api_instance: APIInstance) -> APIInstance:
        """Return an API instance with a search tool and an execute tool."""
        functions = [ToolFunction(api_instance, tool) for tool in api_instance.tools]
        declarations = "\n\n".join(function.declaration for function in functions)
        tools: list[Tool] = [ExecuteTool(self._pool, functions)]
        if len(declarations) <= INLINE_BUDGET:
            catalog = f"These are all the functions:\n```python\n{declarations}\n```"
        else:
            tools.insert(0, SearchTool(functions))
            names = ", ".join(function.name for function in functions)
            catalog = (
                "Get the declaration of a function with the `search` tool before "
                f"you call the function. These are the functions: {names}"
            )

        return APIInstance(
            api=self,
            api_prompt=f"{api_instance.api_prompt}\n{PROMPT}\n{catalog}",
            llm_context=api_instance.llm_context,
            tools=tools,
        )


class ToolFunction:
    """A tool as a function that code can call."""

    def __init__(self, api_instance: APIInstance, tool: Tool) -> None:
        """Init the class."""
        self._api_instance = api_instance
        self._tool_name = tool.name
        self.name = re.sub(r"\W", "_", tool.name)
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
        for name, prop in sorted(
            properties.items(), key=lambda item: item[0] not in required
        ):
            default = "" if name in required else " = None"
            comment = (
                f"  # {' '.join(description.split())}"
                if (description := prop.get("description"))
                else ""
            )
            lines.append(f"    {name}: {_python_type(prop)}{default},{comment}")
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
                result = await self._api_instance.async_call_tool(
                    ToolInput(tool_name=self._tool_name, tool_args=kwargs)
                )
            except (HomeAssistantError, probatio.Invalid) as err:
                return {"error": type(err).__name__, "error_text": str(err)}
            finally:
                tasks.discard(task)
            return result.data

        return call_tool


def _python_type(schema: dict[str, Any]) -> str:
    """Return the Python type hint for a JSON schema."""
    if "enum" in schema:
        return f"Literal[{', '.join(repr(value) for value in schema['enum'])}]"
    if variants := schema.get("anyOf") or schema.get("oneOf"):
        return " | ".join(dict.fromkeys(_python_type(variant) for variant in variants))
    json_type = schema.get("type")
    if isinstance(json_type, list):
        return " | ".join(_python_type({**schema, "type": item}) for item in json_type)
    if json_type == "array":
        return f"list[{_python_type(schema.get('items', {}))}]"
    return _JSON_TYPES.get(str(json_type), "Any")


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
        words = set(_words(tool_input.tool_args["query"]))
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

    def __init__(self, pool: AsyncMonty, functions: list[ToolFunction]) -> None:
        """Init the class."""
        self._pool = pool
        self._functions = functions

    @override
    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: ToolInput,
        llm_context: LLMContext,
    ) -> ToolResult:
        """Run the code."""
        tasks: set[asyncio.Task[Any]] = set()
        output = CollectString(MAX_OUTPUT_BYTES)
        try:
            async with (
                asyncio.timeout(TIMEOUT),
                self._pool.checkout(limits=LIMITS) as session,
            ):
                result = await session.feed_run(
                    tool_input.tool_args["code"],
                    external_lookup={
                        function.name: function.create(tasks)
                        for function in self._functions
                    },
                    print_callback=output,
                )
        except (MontyError, TimeoutError) as err:
            return ToolResult(
                data={"error": str(err) or "Timeout", "output": output.output},
                error=True,
            )
        finally:
            # The sandbox does not stop tool calls that run when the code ends.
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        return ToolResult(
            data={
                # The sandbox can return values that JSON cannot represent, such as sets.
                "result": json.loads(json.dumps(result, default=str)),
                "output": output.output,
            }
        )
