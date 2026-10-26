"""Tests for system_log LLM tools."""

from datetime import datetime
import logging
from pathlib import Path
import time
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
                "INFO (MainThread) [homeassistant.core] Before the window",
                "DEBUG (MainThread) [homeassistant.components.zwave_js] Polling",
            ],
            id="limit_keeps_oldest",
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
            "start_time must not be after end_time",
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
async def test_get_logs_file_line_limit(
    hass: HomeAssistant, llm_context: llm.LLMContext, logs_tool: llm.Tool
) -> None:
    """Test the next page starts at the last record of a full read."""
    with patch("homeassistant.components.system_log.llm.LOG_QUERY_READ_LINES", 3):
        result = await logs_tool.async_call(
            hass, llm.ToolInput(logs_tool.name, {}), llm_context
        )

    # The last record read misses its traceback, so it is on the next page
    assert result.data == {
        "records": [
            {
                "time": "2026-10-20T04:50:00.000-07:00",
                "source": "core",
                "message": (
                    "DEBUG (MainThread) [homeassistant.components.zwave_js] Polling"
                ),
            }
        ],
        "next_start_time": "2026-10-20T04:54:59.900-07:00",
    }


async def test_get_logs_file_error(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    logs_tool: llm.Tool,
    tmp_path: Path,
) -> None:
    """Test a log file that cannot be read is reported as an error."""
    (tmp_path / "home-assistant.log").unlink()

    result = await logs_tool.async_call(
        hass, llm.ToolInput(logs_tool.name, {}), llm_context
    )

    assert result.data == {
        "records": [],
        "errors": {"core": "Could not read the log file"},
    }


async def _async_call_with_logs(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    logs: dict[str, list[str] | HomeAssistantError],
    tool_args: JsonObjectType,
) -> llm.ToolResult:
    """Call the logs tool with the logs as default sources, plus an unread one."""
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
        return await tool.async_call(
            hass, llm.ToolInput(tool.name, tool_args), llm_context
        )


@pytest.mark.usefixtures("frozen_time")
async def test_get_logs_merge_sources(
    hass: HomeAssistant, llm_context: llm.LLMContext, snapshot: SnapshotAssertion
) -> None:
    """Test the sources are merged into one log that is read from the start."""
    result = await _async_call_with_logs(
        hass,
        llm_context,
        {
            "busy": [
                *(
                    f"2026-10-20 13:5{minute}:00.000+02:00 INFO (MainThread) "
                    f"[busy] Message {minute}"
                    for minute in range(10)
                ),
                "2026-10-20 13:59:30.000+02:00 DEBUG (MainThread) [busy] Debug",
            ],
            "quiet": [
                "2026-10-20 13:51:30.000+02:00 quiet[1]: Without a level",
                "2026-10-20 13:52:00.000+02:00 quiet[1]: Same time as busy",
            ],
            "failing": HomeAssistantError("Could not read"),
        },
        {"limit": 4, "level": "info"},
    )

    # The fifth record has the same time as the fourth, so it is included
    assert result == snapshot


@pytest.mark.usefixtures("frozen_time")
async def test_get_logs_source_line_limit(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test the merged log stops where a source stopped reading."""
    with patch("homeassistant.components.system_log.llm.LOG_QUERY_READ_LINES", 3):
        result = await _async_call_with_logs(
            hass,
            llm_context,
            {
                "busy": [
                    f"2026-10-20 13:5{minute}:00.000+02:00 INFO (MainThread) "
                    f"[busy] Message {minute}"
                    for minute in range(3)
                ],
                "quiet": [
                    "2026-10-20 13:51:30.000+02:00 quiet[1]: Before busy stopped",
                    "2026-10-20 13:55:00.000+02:00 quiet[1]: After busy stopped",
                ],
            },
            {},
        )

    assert [record["message"] for record in result.data["records"]] == [
        "INFO (MainThread) [busy] Message 0",
        "INFO (MainThread) [busy] Message 1",
        "quiet[1]: Before busy stopped",
    ]
    assert result.data["next_start_time"] == "2026-10-20T04:51:59.900-07:00"


@pytest.mark.parametrize(
    "lines",
    [
        pytest.param(
            [
                "2026-10-20 13:50:00.000+02:00 ERROR (MainThread) [core] Deep",
                "  File one",
                "  File two",
            ],
            id="one_record",
        ),
        pytest.param(
            [
                f"2026-10-20 13:50:00.000+02:00 INFO (MainThread) [core] {index}"
                for index in range(3)
            ],
            id="records_with_same_time",
        ),
    ],
)
@pytest.mark.usefixtures("frozen_time")
async def test_get_logs_records_fill_line_limit(
    hass: HomeAssistant, llm_context: llm.LLMContext, lines: list[str]
) -> None:
    """Test records with one time that fill all lines are returned."""
    with patch("homeassistant.components.system_log.llm.LOG_QUERY_READ_LINES", 3):
        result = await _async_call_with_logs(hass, llm_context, {"core": lines}, {})

    assert result.data["records"]
    # The next page starts after them, so pages move on
    assert result.data["next_start_time"] == "2026-10-20T04:50:00.001-07:00"


@pytest.mark.parametrize(
    ("log", "pages"),
    [
        pytest.param(
            [
                "13:50:00.000 First",
                "13:50:00.000 Same time",
                "13:50:00.500 Second",
                "13:51:00.000 Third",
            ],
            [
                (["First", "Same time"], "2026-10-20T04:50:00.001-07:00"),
                (["Second"], "2026-10-20T04:50:59.900-07:00"),
                (["Third"], None),
            ],
            id="same_time",
        ),
        pytest.param(
            [
                "13:50:00.000 First",
                "13:50:01.000 Third",
                # Created before the record above, but written after it
                "13:50:00.950 Second",
                "13:50:02.000 Fourth",
            ],
            [
                (["First"], "2026-10-20T04:50:00.900-07:00"),
                (["Second"], "2026-10-20T04:50:00.951-07:00"),
                (["Third"], "2026-10-20T04:50:01.001-07:00"),
                (["Fourth"], None),
            ],
            id="written_out_of_order",
        ),
    ],
)
@pytest.mark.usefixtures("frozen_time")
async def test_get_logs_pages(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    logs_tool: llm.Tool,
    tmp_path: Path,
    log: list[str],
    pages: list[tuple[list[str], str | None]],
) -> None:
    """Test following next_start_time returns every record once."""
    (tmp_path / "home-assistant.log").write_text(
        "".join(
            f"2026-10-20 {time}+02:00 INFO (MainThread) [core] {message}\n"
            for time, message in (line.split(" ", 1) for line in log)
        )
    )
    start_time = "2026-10-20T13:45:00+02:00"

    with patch("homeassistant.components.system_log.llm.LOG_QUERY_READ_LINES", 2):
        for expected_messages, expected_next_start_time in pages:
            result = await logs_tool.async_call(
                hass,
                llm.ToolInput(logs_tool.name, {"start_time": start_time}),
                llm_context,
            )
            assert [record["message"] for record in result.data["records"]] == [
                f"INFO (MainThread) [core] {message}" for message in expected_messages
            ]
            assert result.data.get("next_start_time") == expected_next_start_time
            start_time = expected_next_start_time


@pytest.mark.usefixtures("frozen_time")
async def test_get_logs_pages_to_end_time(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    logs_tool: llm.Tool,
    tmp_path: Path,
) -> None:
    """Test the next page can start at the end time to read a record there."""
    (tmp_path / "home-assistant.log").write_text(
        "2026-10-20 13:50:00.000+02:00 INFO (MainThread) [core] First\n"
        "2026-10-20 13:55:00.000+02:00 INFO (MainThread) [core] At the end\n"
    )
    end_time = "2026-10-20T13:55:00+02:00"

    first = await logs_tool.async_call(
        hass,
        llm.ToolInput(
            logs_tool.name,
            {
                "start_time": "2026-10-20T13:45:00+02:00",
                "end_time": end_time,
                "limit": 1,
            },
        ),
        llm_context,
    )
    second = await logs_tool.async_call(
        hass,
        llm.ToolInput(
            logs_tool.name,
            {"start_time": first.data["next_start_time"], "end_time": end_time},
        ),
        llm_context,
    )

    assert first.data["next_start_time"] == "2026-10-20T04:55:00.000-07:00"
    assert [record["message"] for record in second.data["records"]] == [
        "INFO (MainThread) [core] At the end"
    ]
    assert "next_start_time" not in second.data


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        pytest.param(
            "Headers {'Authorization': 'Bearer abc.def-123', 'Accept': '*/*'}",
            "Headers {'Authorization': 'Bearer ***', 'Accept': '*/*'}",
            id="authorization",
        ),
        pytest.param(
            "GET https://example.com/v1?api_key=XYZ123&page=2",
            "GET https://example.com/v1?api_key=***&page=2",
            id="query",
        ),
        pytest.param(
            'Payload {"access_token": "eyJhbGc", "expires_in": 3600}',
            'Payload {"access_token": "***", "expires_in": 3600}',
            id="json",
        ),
        pytest.param(
            "Login with password=hunter2, retrying",
            "Login with password=***, retrying",
            id="key_value",
        ),
        pytest.param(
            'Payload {"password": "alpha beta", "user": "paulus"}',
            'Payload {"password": "***", "user": "paulus"}',
            id="quoted_with_space",
        ),
        pytest.param(
            r'Payload {"password": "al\"pha", "user": "paulus"}',
            'Payload {"password": "***", "user": "paulus"}',
            id="quoted_with_escaped_quote",
        ),
        pytest.param(
            "ValueError: password=hunter2",
            "ValueError: password=***",
            id="after_other_key",
        ),
        pytest.param(
            "{'url': 'https://example.com/?api_key=XYZ123', 'user': 'paulus'}",
            "{'url': 'https://example.com/?api_key=***', 'user': 'paulus'}",
            id="in_other_value",
        ),
        pytest.param(
            "Invalid token for device kitchen",
            "Invalid token for device kitchen",
            id="prose",
        ),
    ],
)
@pytest.mark.usefixtures("frozen_time")
async def test_get_logs_mask_secrets(
    hass: HomeAssistant, llm_context: llm.LLMContext, message: str, expected: str
) -> None:
    """Test values that look like credentials are masked."""
    result = await _async_call_with_logs(
        hass,
        llm_context,
        {
            "core": [
                f"2026-10-20 13:50:00.000+02:00 DEBUG (MainThread) [core] {message}",
                # Lines of a traceback are masked too
                f"  {message}",
            ]
        },
        {},
    )

    assert result.data["records"][0]["message"] == (
        f"DEBUG (MainThread) [core] {expected}\n  {expected}"
    )


@pytest.mark.usefixtures("frozen_time")
async def test_get_logs_contains_secret(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test a masked value cannot be found with contains."""
    result = await _async_call_with_logs(
        hass,
        llm_context,
        {
            "core": [
                "2026-10-20 13:50:00.000+02:00 DEBUG (MainThread) [core] "
                'Login with {"password": "hunter2 beta"}'
            ]
        },
        {"contains": "beta"},
    )

    assert result.data["records"] == []


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("a" * 200_000, id="word"),
        pytest.param("token" * 40_000, id="word_of_secret_names"),
    ],
)
async def test_get_logs_mask_long_payload(
    hass: HomeAssistant, llm_context: llm.LLMContext, payload: str
) -> None:
    """Test masking a long payload without secrets takes linear time."""

    start = time.monotonic()
    result = await _async_call_with_logs(
        hass,
        llm_context,
        {
            "core": [
                f"2026-10-20 13:50:00.000+02:00 DEBUG (MainThread) [core] {payload}"
            ]
        },
        # The time is not frozen, so it can be measured
        {
            "start_time": "2026-10-20T13:45:00+02:00",
            "end_time": "2026-10-20T14:00:00+02:00",
        },
    )

    # Quadratic masking takes minutes for this payload
    assert time.monotonic() - start < 2
    assert result.data["records"][0]["message"].startswith(
        f"DEBUG (MainThread) [core] {payload[:100]}"
    )


@pytest.mark.usefixtures("frozen_time")
async def test_get_logs_shorten_record(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test a long record keeps its start and its end."""
    result = await _async_call_with_logs(
        hass,
        llm_context,
        {
            "core": [
                "2026-10-20 13:50:00.000+02:00 ERROR (MainThread) [core] Failed",
                "Traceback (most recent call last):",
                *(f'  File "frame_{index}.py", line 1, in run' for index in range(200)),
                "ValueError: Boom",
            ]
        },
        {},
    )

    message = result.data["records"][0]["message"]
    assert message.startswith("ERROR (MainThread) [core] Failed\nTraceback")
    assert "characters left out" in message
    assert message.endswith("in run\nValueError: Boom")
    # The end keeps the innermost frames
    assert 'File "frame_199.py"' in message
    assert len(message) < 1100


@pytest.mark.parametrize(
    ("max_characters", "expected_messages", "next_start_time"),
    [
        pytest.param(
            25,
            ["INFO (MainThread) [busy] Message 0"],
            "2026-10-20T04:51:00.000-07:00",
            id="first_record_over_budget",
        ),
        pytest.param(
            70,
            [
                "INFO (MainThread) [busy] Message 0",
                "INFO (MainThread) [busy] Message 1",
            ],
            "2026-10-20T04:52:00.000-07:00",
            id="two_records",
        ),
        pytest.param(
            100,
            [
                "INFO (MainThread) [busy] Message 0",
                "INFO (MainThread) [busy] Message 1",
            ],
            "2026-10-20T04:52:00.000-07:00",
            id="records_with_same_time_not_split",
        ),
        pytest.param(
            125,
            [
                "INFO (MainThread) [busy] Message 0",
                "INFO (MainThread) [busy] Message 1",
                "INFO (MainThread) [busy] Message 2",
                "quiet[1]: Same time",
            ],
            "2026-10-20T04:53:00.000-07:00",
            id="records_with_same_time",
        ),
    ],
)
@pytest.mark.usefixtures("frozen_time")
async def test_get_logs_character_budget(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    max_characters: int,
    expected_messages: list[str],
    next_start_time: str,
) -> None:
    """Test a page ends when its messages reach the character budget."""
    with patch(
        "homeassistant.components.system_log.llm.LOG_QUERY_MAX_CHARACTERS",
        max_characters,
    ):
        result = await _async_call_with_logs(
            hass,
            llm_context,
            {
                "busy": [
                    f"2026-10-20 13:5{minute}:00.000+02:00 INFO (MainThread) "
                    f"[busy] Message {minute}"
                    for minute in range(4)
                ],
                "quiet": ["2026-10-20 13:52:00.000+02:00 quiet[1]: Same time"],
            },
            {},
        )

    assert [record["message"] for record in result.data["records"]] == (
        expected_messages
    )
    assert result.data["next_start_time"] == next_start_time


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
