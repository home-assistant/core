"""Tests for the Code Mode LLM API."""

import asyncio
from typing import override
from unittest.mock import patch

import probatio
import pytest

from homeassistant.components.code_mode import api as code_mode_api
from homeassistant.components.conversation import DATA_CODE_MODE
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, llm
from homeassistant.setup import async_setup_component


class GetStateTool(llm.Tool):
    """Tool that returns a fake state."""

    name = "test__get-state"
    description = "Get the state\nof an entity"
    parameters = probatio.Schema(
        {
            probatio.Required("entity_id", description="The entity"): cv.string,
            probatio.Optional("attributes"): [probatio.In(["brightness", "color"])],
            probatio.Optional("retries"): probatio.Any(int, None),
        }
    )
    integration = "test"

    def __init__(self) -> None:
        """Init the class."""
        self.calls: list[str] = []

    @override
    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> llm.ToolResult:
        """Return a fake state."""
        entity_id = tool_input.tool_args["entity_id"]
        if entity_id == "light.broken":
            raise HomeAssistantError("Light is broken")
        if entity_id == "light.slow":
            await asyncio.sleep(10)
        self.calls.append(entity_id)
        state = "on" if entity_id.endswith(("0", "5")) else "off"
        return llm.ToolResult(data={"entity_id": entity_id, "state": state})


class TestAPI(llm.API):
    """API with a test tool."""

    __test__ = False

    def __init__(self, hass: HomeAssistant, tool: llm.Tool) -> None:
        """Init the class."""
        super().__init__(hass=hass, id="test", name="Test")
        self.tool = tool

    @override
    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the instance of the API."""
        return llm.APIInstance(
            api=self,
            api_prompt="Test prompt.",
            llm_context=llm_context,
            tools=[self.tool],
        )


@pytest.fixture
def llm_context() -> llm.LLMContext:
    """Return an LLM context."""
    return llm.LLMContext(
        platform="test_platform",
        context=Context(),
        language="*",
        assistant="conversation",
        device_id=None,
    )


@pytest.fixture
def state_tool() -> GetStateTool:
    """Return the test tool."""
    return GetStateTool()


@pytest.fixture(autouse=True)
async def setup_integration(hass: HomeAssistant, state_tool: GetStateTool) -> None:
    """Set up Code Mode and the test API."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "code_mode", {})
    llm.async_register_api(hass, TestAPI(hass, state_tool))


async def _api_instance(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> llm.APIInstance:
    """Return the Assist API and the test API with their tools as code."""
    return hass.data[DATA_CODE_MODE](
        await llm.async_get_api(hass, [llm.LLM_API_ASSIST, "test"], llm_context)
    )


@pytest.fixture
async def api_instance(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> llm.APIInstance:
    """Return the Assist API and the test API with their tools as code."""
    return await _api_instance(hass, llm_context)


async def _execute(api_instance: llm.APIInstance, code: str) -> llm.ToolResult:
    """Run code with the execute tool."""
    return await api_instance.async_call_tool(llm.ToolInput("execute", {"code": code}))


async def test_declarations_in_prompt(api_instance: llm.APIInstance) -> None:
    """Test a small API has only the execute tool and declares its functions."""
    assert [tool.name for tool in api_instance.tools] == ["execute"]
    assert api_instance.api.id == "assist|test"
    assert "Test prompt." in api_instance.api_prompt
    assert "async def llm__GetDateTime() -> dict:" in api_instance.api_prompt
    assert (
        """async def test__get_state(
    *,
    entity_id: str,  # The entity
    attributes: list[Literal['brightness', 'color']] = None,
    retries: int | None = None,
) -> dict:
    \"\"\"Get the state of an entity\"\"\""""
        in api_instance.api_prompt
    )


async def test_search_for_large_api(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test a large API lists function names and adds the search tool."""
    with patch.object(code_mode_api, "INLINE_BUDGET", 100):
        api_instance = await _api_instance(hass, llm_context)

    assert [tool.name for tool in api_instance.tools] == ["search", "execute"]
    assert "async def" not in api_instance.api_prompt
    assert "llm__GetDateTime, test__get_state" in api_instance.api_prompt

    result = await api_instance.async_call_tool(
        llm.ToolInput("search", {"query": "state of an entity"})
    )
    assert result.data["functions"][0].startswith("async def test__get_state(")

    result = await api_instance.async_call_tool(
        llm.ToolInput("search", {"query": "GetDateTime"})
    )
    assert result.data["functions"][0] == (
        'async def llm__GetDateTime() -> dict:\n    """Provides the current date and time."""'
    )

    result = await api_instance.async_call_tool(
        llm.ToolInput("search", {"query": "vacuum"})
    )
    assert result.data == {"functions": []}


async def test_execute_calls_tools(
    api_instance: llm.APIInstance, state_tool: GetStateTool
) -> None:
    """Test the code calls tools from every wrapped API in parallel."""
    result = await _execute(
        api_instance,
        """
import asyncio
ids = [f"light.room_{i}" for i in range(10)]
states = await asyncio.gather(*[test__get_state(entity_id=i) for i in ids])
now = await llm__GetDateTime()
print("checked", len(states))
{"on": [s["entity_id"] for s in states if s["state"] == "on"], "has_date": "date" in now}
""",
    )

    assert result.error is False
    assert result.data == {
        "result": {"on": ["light.room_0", "light.room_5"], "has_date": True},
        "output": "checked 10\n",
    }
    assert len(state_tool.calls) == 10


async def test_tool_error_is_returned_to_code(api_instance: llm.APIInstance) -> None:
    """Test a failing tool gives the code an error dict."""
    result = await _execute(
        api_instance, 'await test__get_state(entity_id="light.broken")'
    )

    assert result.data["result"] == {
        "error": "HomeAssistantError",
        "error_text": "Light is broken",
    }


@pytest.mark.parametrize(
    ("code", "error"),
    [
        ("await execute(code='1')", "NameError"),
        ("open('/etc/passwd').read()", "PermissionError"),
        ("import socket", "ModuleNotFoundError"),
        ("().__class__", "AttributeError"),
        ("x = 'a' * 10**10", "MemoryError"),
        ("1 +", "Expected an expression"),
    ],
)
async def test_sandbox(api_instance: llm.APIInstance, code: str, error: str) -> None:
    """Test the sandbox blocks access and reports errors."""
    result = await _execute(api_instance, code)

    assert result.error is True
    assert error in result.data["error"]


async def test_cpu_limit(api_instance: llm.APIInstance) -> None:
    """Test a busy loop is stopped."""
    with patch.dict(code_mode_api.LIMITS, {"max_feed_duration_secs": 0.1}):
        result = await _execute(api_instance, "while True: pass")

    assert result.error is True
    assert "TimeoutError" in result.data["error"]


async def test_wall_clock_limit(api_instance: llm.APIInstance) -> None:
    """Test a slow tool call is stopped."""
    with patch.object(code_mode_api, "TIMEOUT", 0.1):
        result = await _execute(
            api_instance, 'await test__get_state(entity_id="light.slow")'
        )

    assert result.error is True
    assert result.data == {"error": "Timeout", "output": ""}


async def test_result_is_json(api_instance: llm.APIInstance) -> None:
    """Test values that JSON cannot represent are converted."""
    result = await _execute(api_instance, "{'items': (1, 2), 'when': {1}}")

    assert result.data["result"] == {"items": [1, 2], "when": "{1}"}
