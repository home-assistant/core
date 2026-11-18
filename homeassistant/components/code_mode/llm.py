"""LLM tool that runs sandboxed code calling the other tools."""

import asyncio
from collections.abc import Callable, Coroutine
import json
import re
from typing import Any, override

import probatio
from pydantic_monty import AsyncMonty, CollectString, MontyError, ResourceLimits

from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.llm import (
    APIInstance,
    LLMContext,
    Tool,
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


class RunCodeTool(Tool):
    """Tool for running code that calls the other tools of the API."""

    name = "code_mode__run"
    title = "Run code"
    description = (
        "Run Python code in a sandbox to use several tools in one step. "
        "Use it to chain tool calls, to repeat a tool call for many targets, "
        "or to filter a large tool result. "
        "Every other tool is an async function with the name of the tool. "
        "Pass the tool parameters as keyword arguments and await the call. "
        "The call returns a dict. "
        "Run calls in parallel with asyncio.gather. "
        "The tool returns the value of the last expression and the printed output. "
        "The code cannot import other modules or access files or the network."
    )
    parameters = probatio.Schema(
        {probatio.Required("code", description="Python source code"): cv.string}
    )
    integration = DOMAIN

    def __init__(self, pool: AsyncMonty) -> None:
        """Init the class."""
        self._pool = pool
        self._api_instance: APIInstance | None = None

    @override
    def __eq__(self, other: object) -> bool:
        """All instances are interchangeable when APIs are merged."""
        if type(self) is type(other) is RunCodeTool:
            return True
        return NotImplemented

    @callback
    @override
    def async_set_api_instance(self, api_instance: APIInstance) -> None:
        """Store the API instance whose tools the code can call."""
        self._api_instance = api_instance

    @override
    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: ToolInput,
        llm_context: LLMContext,
    ) -> ToolResult:
        """Run the code."""
        if (api_instance := self._api_instance) is None:
            raise HomeAssistantError("The tool is not part of an API instance")

        tasks: set[asyncio.Task[Any]] = set()
        functions = {
            re.sub(r"\W", "_", tool.name): _tool_function(
                api_instance, tool.name, tasks
            )
            for tool in api_instance.tools
            if tool != self
        }
        output = CollectString(MAX_OUTPUT_BYTES)
        try:
            async with (
                asyncio.timeout(TIMEOUT),
                self._pool.checkout(limits=LIMITS) as session,
            ):
                result = await session.feed_run(
                    tool_input.tool_args["code"],
                    external_lookup=functions,
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


def _tool_function(
    api_instance: APIInstance, tool_name: str, tasks: set[asyncio.Task[Any]]
) -> Callable[..., Coroutine[Any, Any, JsonObjectType]]:
    """Return the sandbox function that calls a tool."""

    async def call_tool(**kwargs: Any) -> JsonObjectType:
        task = asyncio.current_task()
        assert task is not None
        tasks.add(task)
        try:
            result = await api_instance.async_call_tool(
                ToolInput(tool_name=tool_name, tool_args=kwargs)
            )
        except (HomeAssistantError, probatio.Invalid) as err:
            return {"error": type(err).__name__, "error_text": str(err)}
        finally:
            tasks.discard(task)
        return result.data

    return call_tool


@callback
def async_get_tools(
    hass: HomeAssistant, llm_context: LLMContext, api_id: str
) -> LLMTools | None:
    """Return the run code tool when the integration is set up."""
    if not (entries := hass.config_entries.async_loaded_entries(DOMAIN)):
        return None
    return LLMTools(tools=[RunCodeTool(entries[0].runtime_data)])
