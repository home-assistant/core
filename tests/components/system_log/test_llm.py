"""Tests for system_log LLM tools."""

import logging

import probatio
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import system_log
from homeassistant.components.system_log.llm import (
    SystemLogGetEntriesTool,
    async_get_tools,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonObjectType

from tests.common import MockUser

_LOGGER = logging.getLogger("test_system_log_llm")
_OTHER_LOGGER = logging.getLogger("custom_integration")


@pytest.fixture
def llm_context() -> llm.LLMContext:
    """Return an LLM context."""
    return llm.LLMContext(
        platform="test",
        context=None,
        language="*",
        assistant="conversation",
        device_id=None,
    )


async def test_async_get_tools(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test async_get_tools returns tools only for Home Assistant API."""
    assert async_get_tools(hass, llm_context, llm.LLM_API_ASSIST) is None

    home_assistant_tools = async_get_tools(
        hass, llm_context, llm.LLM_API_HOME_ASSISTANT
    )
    assert home_assistant_tools is not None
    assert len(home_assistant_tools.tools) == 1
    assert home_assistant_tools.tools[0].name == "system_log__get_entries"
    assert home_assistant_tools.prompt is None


def test_parameters_openapi(snapshot: SnapshotAssertion) -> None:
    """Test that the tool schema can be exported for LLM clients."""
    assert probatio.to_openapi(SystemLogGetEntriesTool.parameters) == snapshot


@pytest.mark.parametrize(
    "tool_args",
    [
        pytest.param({"level": "debug"}, id="unsupported_level"),
        pytest.param({"limit": 0}, id="limit_below_minimum"),
        pytest.param({"limit": 51}, id="limit_above_maximum"),
        pytest.param({"logger": []}, id="invalid_logger"),
        pytest.param({"include_traceback": "invalid"}, id="invalid_boolean"),
        pytest.param({"unknown": True}, id="unknown_argument"),
    ],
)
async def test_invalid_parameters(
    hass: HomeAssistant, llm_context: llm.LLMContext, tool_args: JsonObjectType
) -> None:
    """Test invalid arguments are rejected by the Probatio schema."""
    assert await async_setup_component(hass, system_log.DOMAIN, {})
    tool = SystemLogGetEntriesTool()

    with pytest.raises(probatio.Invalid):
        await tool.async_call(hass, llm.ToolInput(tool.name, tool_args), llm_context)


async def test_call_through_api(
    hass: HomeAssistant, hass_admin_user: MockUser, llm_context: llm.LLMContext
) -> None:
    """Test tool discovery and structured results through the Home Assistant API."""
    assert await async_setup_component(hass, system_log.DOMAIN, {})
    assert await async_setup_component(hass, "llm", {})
    llm_context.context = Context(user_id=hass_admin_user.id)

    api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)
    tool = next(tool for tool in api.tools if tool.name == "system_log__get_entries")
    assert tool.integration == system_log.DOMAIN
    assert tool.annotations == llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    assert await api.async_call_tool(llm.ToolInput(tool.name, {})) == llm.ToolResult(
        data={"result": []}
    )


async def test_system_log_not_loaded(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test tool error when system_log is not loaded in hass.data."""
    tool = SystemLogGetEntriesTool()
    tool_input = llm.ToolInput(tool_name=tool.name, tool_args={})
    result = await tool.async_call(hass, tool_input, llm_context)

    assert result == llm.ToolResult(
        data={"error": "System log integration is not loaded."}, error=True
    )


async def test_get_entries_default(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test retrieving entries with default arguments."""
    assert await async_setup_component(hass, system_log.DOMAIN, {})
    await hass.async_block_till_done()

    _LOGGER.error("Test error message")
    _LOGGER.warning("Test warning message")

    tool = SystemLogGetEntriesTool()
    tool_input = llm.ToolInput(tool_name=tool.name, tool_args={})
    result = await tool.async_call(hass, tool_input, llm_context)

    assert result.error is False
    entries = result.data["result"]
    assert len(entries) == 2

    # Most recent entry first
    assert entries[0]["level"] == "WARNING"
    assert entries[0]["message"] == ["Test warning message"]
    assert entries[0]["name"] == "test_system_log_llm"
    assert "exception" not in entries[0]
    assert "timestamp" in entries[0]
    assert "first_occurred" in entries[0]
    assert entries[0]["count"] == 1

    assert entries[1]["level"] == "ERROR"
    assert entries[1]["message"] == ["Test error message"]
    assert "exception" not in entries[1]


@pytest.mark.parametrize(
    "include_traceback",
    [pytest.param(True, id="boolean"), pytest.param("true", id="string")],
)
async def test_get_entries_with_traceback(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    include_traceback: bool | str,
) -> None:
    """Test retrieving entries with exception traceback included."""
    assert await async_setup_component(hass, system_log.DOMAIN, {})
    await hass.async_block_till_done()

    def _raise_error() -> None:
        raise ValueError("Something went wrong")

    try:
        _raise_error()
    except ValueError:
        _LOGGER.exception("Caught an exception")

    tool = SystemLogGetEntriesTool()
    tool_input_no_tb = llm.ToolInput(
        tool_name=tool.name, tool_args={"include_traceback": False}
    )
    result_no_tb = await tool.async_call(hass, tool_input_no_tb, llm_context)
    assert result_no_tb.error is False
    assert "exception" not in result_no_tb.data["result"][0]

    tool_input_tb = llm.ToolInput(
        tool_name=tool.name, tool_args={"include_traceback": include_traceback}
    )
    result_tb = await tool.async_call(hass, tool_input_tb, llm_context)
    assert result_tb.error is False
    assert (
        "ValueError: Something went wrong" in result_tb.data["result"][0]["exception"]
    )


@pytest.mark.parametrize(
    ("filter_level", "expected_levels"),
    [
        pytest.param("error", ["ERROR"], id="filter_error"),
        pytest.param("WARNING", ["WARNING"], id="filter_warning_uppercase"),
        pytest.param("critical", [], id="filter_no_match"),
    ],
)
async def test_filter_by_level(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    filter_level: str,
    expected_levels: list[str],
) -> None:
    """Test filtering entries by level."""
    assert await async_setup_component(hass, system_log.DOMAIN, {})
    await hass.async_block_till_done()

    _LOGGER.error("An error occurred")
    _LOGGER.warning("A warning occurred")

    tool = SystemLogGetEntriesTool()
    tool_input = llm.ToolInput(tool_name=tool.name, tool_args={"level": filter_level})
    result = await tool.async_call(hass, tool_input, llm_context)

    assert result.error is False
    assert [entry["level"] for entry in result.data["result"]] == expected_levels


@pytest.mark.parametrize(
    ("logger_query", "expected_names"),
    [
        pytest.param("test_system", ["test_system_log_llm"], id="match_test_logger"),
        pytest.param(
            "custom_integration", ["custom_integration"], id="match_custom_logger"
        ),
        pytest.param(
            "test_llm",
            ["custom_integration", "test_system_log_llm"],
            id="match_source_path",
        ),
        pytest.param("nonexistent", [], id="no_match"),
    ],
)
async def test_filter_by_logger(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    logger_query: str,
    expected_names: list[str],
) -> None:
    """Test filtering entries by logger name."""
    assert await async_setup_component(hass, system_log.DOMAIN, {})
    await hass.async_block_till_done()

    _LOGGER.error("Error from primary logger")
    _OTHER_LOGGER.error("Error from other logger")

    tool = SystemLogGetEntriesTool()
    tool_input = llm.ToolInput(tool_name=tool.name, tool_args={"logger": logger_query})
    result = await tool.async_call(hass, tool_input, llm_context)

    assert result.error is False
    assert [entry["name"] for entry in result.data["result"]] == expected_names


async def test_limit(hass: HomeAssistant, llm_context: llm.LLMContext) -> None:
    """Test limiting the number of returned entries."""
    assert await async_setup_component(hass, system_log.DOMAIN, {})
    await hass.async_block_till_done()

    for i in range(5):
        logging.getLogger(f"test_logger_{i}").error("Error message %d", i)

    tool = SystemLogGetEntriesTool()
    tool_input = llm.ToolInput(tool_name=tool.name, tool_args={"limit": 2})
    result = await tool.async_call(hass, tool_input, llm_context)

    assert result.error is False
    assert len(result.data["result"]) == 2
