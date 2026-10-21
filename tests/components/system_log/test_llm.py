"""Tests for system_log LLM tools."""

from datetime import datetime
import logging
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from pytest_homeassistant.common import MockUser
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import system_log
from homeassistant.components.system_log.llm import (
    SystemLogGetEntriesTool,
    SystemLogGetLogsTool,
    async_get_tools,
)
from homeassistant.const import KEY_DATA_LOGGING
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import JsonObjectType

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


LOG_FILE = """\
2026-10-20 13:40:00.000+02:00 INFO (MainThread) [homeassistant.core] Before the window
2026-10-20 13:50:00.000 ERROR (MainThread) [homeassistant.old] Without an offset
2026-10-20 13:50:00.000+02:00 DEBUG (MainThread) [homeassistant.components.zwave_js] Polling
2026-10-20 13:55:00.000+02:00 ERROR (MainThread) [homeassistant.components.zwave_js] Connection lost
Traceback (most recent call last):
ValueError: Boom
2026-10-20 13:58:00.000+02:00 WARNING (MainThread) [homeassistant.components.hue] Slow update
"""


@pytest.fixture
def frozen_time(freezer: FrozenDateTimeFactory) -> None:
    """Freeze the time to 14:00 at the UTC offset of the logs."""
    freezer.move_to("2026-10-20 12:00:00+00:00")


@pytest.fixture
def logs_tool(
    hass: HomeAssistant, tmp_path: Path, llm_context: llm.LLMContext
) -> llm.Tool:
    """Return the logs tool for a log file."""
    path = tmp_path / "home-assistant.log"
    path.write_text(LOG_FILE)
    hass.data[KEY_DATA_LOGGING] = str(path)
    tools = async_get_tools(hass, llm_context, llm.LLM_API_HOME_ASSISTANT)
    assert tools is not None
    return tools.tools[1]


@pytest.mark.parametrize(
    ("data", "components", "expected_tools"),
    [
        pytest.param(
            {KEY_DATA_LOGGING: "home-assistant.log"},
            set(),
            ["system_log__get_entries", "system_log__get_logs"],
            id="log_file",
        ),
        pytest.param({}, set(), ["system_log__get_entries"], id="no_log_file"),
        pytest.param(
            {KEY_DATA_LOGGING: "home-assistant.log"},
            {"hassio"},
            ["system_log__get_entries"],
            id="supervisor",
        ),
    ],
)
async def test_async_get_tools_logs(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    data: dict[HassKey[str], str],
    components: set[str],
    expected_tools: list[str],
) -> None:
    """Test the logs tool is only provided for a log file without Supervisor."""
    hass.data.update(data)
    hass.config.components.update(components)

    tools = async_get_tools(hass, llm_context, llm.LLM_API_HOME_ASSISTANT)

    assert tools is not None
    assert [tool.name for tool in tools.tools] == expected_tools


def test_logs_parameters_openapi(snapshot: SnapshotAssertion) -> None:
    """Test that the logs tool schema can be exported for LLM clients."""
    tool = SystemLogGetLogsTool(
        {"core": "Home Assistant", "host": "the operating system"}, ["core"]
    )

    assert probatio.to_openapi(tool.parameters) == snapshot


@pytest.mark.usefixtures("frozen_time")
async def test_get_logs_default(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    logs_tool: llm.Tool,
    snapshot: SnapshotAssertion,
) -> None:
    """Test reading the last 15 minutes of the log file."""
    result = await logs_tool.async_call(
        hass, llm.ToolInput(logs_tool.name, {}), llm_context
    )

    assert result == snapshot


@pytest.mark.parametrize(
    ("tool_args", "expected_messages"),
    [
        pytest.param(
            {"level": "warning"},
            [
                "ERROR (MainThread) [homeassistant.components.zwave_js] Connection lost",
                "WARNING (MainThread) [homeassistant.components.hue] Slow update",
            ],
            id="level",
        ),
        pytest.param(
            {"contains": "boom"},
            [
                "ERROR (MainThread) [homeassistant.components.zwave_js] Connection lost",
            ],
            id="contains_traceback",
        ),
        pytest.param(
            {"contains": "ZWAVE_JS"},
            [
                "DEBUG (MainThread) [homeassistant.components.zwave_js] Polling",
                "ERROR (MainThread) [homeassistant.components.zwave_js] Connection lost",
            ],
            id="contains_logger",
        ),
        pytest.param(
            {"start_time": "2026-10-20T13:30:00+02:00", "limit": 2},
            [
                "ERROR (MainThread) [homeassistant.components.zwave_js] Connection lost",
                "WARNING (MainThread) [homeassistant.components.hue] Slow update",
            ],
            id="limit_keeps_newest",
        ),
        pytest.param(
            {
                "start_time": "2026-10-20T13:30:00+02:00",
                "end_time": "2026-10-20T13:45:00+02:00",
            },
            ["INFO (MainThread) [homeassistant.core] Before the window"],
            id="time_window",
        ),
    ],
)
@pytest.mark.usefixtures("frozen_time")
async def test_get_logs_filters(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    logs_tool: llm.Tool,
    tool_args: JsonObjectType,
    expected_messages: list[str],
) -> None:
    """Test filtering the records of the log file."""
    result = await logs_tool.async_call(
        hass, llm.ToolInput(logs_tool.name, tool_args), llm_context
    )

    assert [
        record["message"].partition("\n")[0] for record in result.data["records"]
    ] == expected_messages


@pytest.mark.parametrize(
    ("tool_args", "error"),
    [
        pytest.param({"end_time": "yesterday"}, "Invalid end_time", id="end_time"),
        pytest.param({"start_time": "today"}, "Invalid start_time", id="start_time"),
        pytest.param(
            {
                "start_time": "2026-10-20T14:00:00+02:00",
                "end_time": "2026-10-20T13:00:00+02:00",
            },
            "start_time must be before end_time",
            id="reversed",
        ),
    ],
)
async def test_get_logs_invalid_time(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    logs_tool: llm.Tool,
    tool_args: JsonObjectType,
    error: str,
) -> None:
    """Test invalid time windows are reported."""
    result = await logs_tool.async_call(
        hass, llm.ToolInput(logs_tool.name, tool_args), llm_context
    )

    assert result == llm.ToolResult(data={"error": error}, error=True)


@pytest.mark.usefixtures("frozen_time")
async def test_get_logs_not_read_before(
    hass: HomeAssistant, llm_context: llm.LLMContext, logs_tool: llm.Tool
) -> None:
    """Test reporting a time window that starts before the lines read."""
    with patch("homeassistant.components.system_log.llm.LOG_QUERY_READ_LINES", 3):
        result = await logs_tool.async_call(
            hass, llm.ToolInput(logs_tool.name, {}), llm_context
        )

    # Continuation lines of a record that was not read are dropped
    assert len(result.data["records"]) == 1
    assert result.data["sources"] == {
        "core": {
            "matched": 1,
            "returned": 1,
            "not_read_before": "2026-10-20T04:58:00.000-07:00",
        }
    }


@pytest.mark.usefixtures("frozen_time")
async def test_get_logs_merge_sources(
    hass: HomeAssistant, llm_context: llm.LLMContext, snapshot: SnapshotAssertion
) -> None:
    """Test the default sources are merged and the limit is split fairly."""
    logs: dict[str, list[str] | HomeAssistantError] = {
        "busy": [
            *(
                f"2026-10-20 13:5{minute}:00.000+02:00 INFO (MainThread) "
                f"[busy] Message {minute}"
                for minute in range(10)
            ),
            "2026-10-20 13:59:30.000+02:00 DEBUG (MainThread) [busy] Debug",
        ],
        "quiet": ["2026-10-20 13:52:30.000+02:00 quiet[1]: Without a level"],
        "failing": HomeAssistantError("Could not read"),
    }
    tool = SystemLogGetLogsTool(
        dict.fromkeys((*logs, "other"), "a test log"), list(logs)
    )

    async def _read_source(
        hass: HomeAssistant,
        source: str,
        start_time: datetime,
        end_time: datetime,
        lines: int,
    ) -> list[str]:
        if isinstance(log := logs[source], HomeAssistantError):
            raise log
        return log

    with patch.object(tool, "async_read_source", side_effect=_read_source):
        result = await tool.async_call(
            hass, llm.ToolInput(tool.name, {"limit": 4, "level": "info"}), llm_context
        )

    assert result == snapshot


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(["unknown"], id="unknown_source"),
        pytest.param([], id="empty"),
    ],
)
async def test_get_logs_invalid_source(
    hass: HomeAssistant, llm_context: llm.LLMContext, source: list[str]
) -> None:
    """Test only available sources are accepted."""
    tool = SystemLogGetLogsTool({"core": "Home Assistant"}, ["core"])

    with pytest.raises(probatio.Invalid):
        await tool.async_call(
            hass, llm.ToolInput(tool.name, {"source": source}), llm_context
        )
