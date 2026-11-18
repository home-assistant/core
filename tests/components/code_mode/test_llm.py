"""Tests for the Code Mode LLM tool."""

import asyncio
from typing import override
from unittest.mock import patch

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.code_mode import llm as code_mode_llm
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, llm
from homeassistant.setup import async_setup_component

TOOL_NAME = "code_mode__run"


class GetStateTool(llm.Tool):
    """Tool that returns a fake state."""

    name = "test__get-state"
    description = "Get a state"
    parameters = probatio.Schema({probatio.Required("entity_id"): cv.string})
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
            api=self, api_prompt="", llm_context=llm_context, tools=[self.tool]
        )


@pytest.fixture
def state_tool() -> GetStateTool:
    """Return the test tool."""
    return GetStateTool()


@pytest.fixture
async def api_instance(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, state_tool: GetStateTool
) -> llm.APIInstance:
    """Return the Assist API merged with the test API, with Code Mode set up."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "llm", {})
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    llm.async_register_api(hass, TestAPI(hass, state_tool))

    return await llm.async_get_api(
        hass,
        [llm.LLM_API_ASSIST, "test"],
        llm.LLMContext(
            platform="test_platform",
            context=Context(),
            language="*",
            assistant="conversation",
            device_id=None,
        ),
    )


async def _run(api_instance: llm.APIInstance, code: str) -> llm.ToolResult:
    """Run code with the tool."""
    return await api_instance.async_call_tool(llm.ToolInput(TOOL_NAME, {"code": code}))


async def test_tool_not_offered_without_entry(hass: HomeAssistant) -> None:
    """Test the tool is absent when the integration has no loaded entry."""
    assert code_mode_llm.async_get_tools(hass, None, llm.LLM_API_ASSIST) is None


@pytest.mark.usefixtures("api_instance")
async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unloading the entry removes the tool."""
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert code_mode_llm.async_get_tools(hass, None, llm.LLM_API_ASSIST) is None


@pytest.mark.usefixtures("api_instance")
async def test_tool_without_api_instance(hass: HomeAssistant) -> None:
    """Test the tool fails when no API instance exposes it."""
    tool = code_mode_llm.async_get_tools(hass, None, llm.LLM_API_ASSIST).tools[0]

    with pytest.raises(HomeAssistantError):
        await tool.async_call(hass, llm.ToolInput(TOOL_NAME, {"code": "1"}), None)


async def test_calls_tools_of_merged_api(
    api_instance: llm.APIInstance, state_tool: GetStateTool
) -> None:
    """Test the code calls tools from every merged API in parallel."""
    result = await _run(
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
    result = await _run(api_instance, 'await test__get_state(entity_id="light.broken")')

    assert result.data["result"] == {
        "error": "HomeAssistantError",
        "error_text": "Light is broken",
    }


async def test_cannot_call_itself(api_instance: llm.APIInstance) -> None:
    """Test the code cannot start nested code runs."""
    result = await _run(api_instance, 'await code_mode__run(code="1")')

    assert result.error is True
    assert "NameError" in result.data["error"]


@pytest.mark.parametrize(
    ("code", "error"),
    [
        ("open('/etc/passwd').read()", "PermissionError"),
        ("import socket", "ModuleNotFoundError"),
        ("().__class__", "AttributeError"),
        ("x = 'a' * 10**10", "MemoryError"),
        ("1 +", "Expected an expression"),
    ],
)
async def test_sandbox(api_instance: llm.APIInstance, code: str, error: str) -> None:
    """Test the sandbox blocks access and reports errors."""
    result = await _run(api_instance, code)

    assert result.error is True
    assert error in result.data["error"]


async def test_cpu_limit(api_instance: llm.APIInstance) -> None:
    """Test a busy loop is stopped."""
    with patch.dict(code_mode_llm.LIMITS, {"max_feed_duration_secs": 0.1}):
        result = await _run(api_instance, "while True: pass")

    assert result.error is True
    assert "TimeoutError" in result.data["error"]


async def test_wall_clock_limit(api_instance: llm.APIInstance) -> None:
    """Test a slow tool call is stopped."""
    with patch.object(code_mode_llm, "TIMEOUT", 0.1):
        result = await _run(
            api_instance, 'await test__get_state(entity_id="light.slow")'
        )

    assert result.error is True
    assert result.data == {"error": "Timeout", "output": ""}


async def test_result_is_json(api_instance: llm.APIInstance) -> None:
    """Test values that JSON cannot represent are converted."""
    result = await _run(api_instance, "{'items': (1, 2), 'when': {1}}")

    assert result.data["result"] == {"items": [1, 2], "when": "{1}"}
