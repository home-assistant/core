"""Tests for the Hass.io LLM tools."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, call, patch

from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.hassio.const import DATA_ADDONS_LIST, DATA_COMPONENT
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.components.hassio.llm import SupervisorGetLogsTool, async_get_tools
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

LOGS = {
    "/core/logs": (
        "2026-10-20 13:55:00.000+02:00 ERROR (MainThread) "
        "[homeassistant.components.mqtt] Disconnected\n"
        "2026-10-20 13:57:00.000+02:00 INFO (MainThread) "
        "[homeassistant.components.mqtt] Connected\n"
    ),
    "/supervisor/logs": (
        "2026-10-20 13:56:00.000+02:00 INFO (MainThread) "
        "[supervisor.apps.app] App core_mosquitto restarted\n"
    ),
    "/host/logs": (
        "2026-10-20 13:54:00.000+02:00 homeassistant kernel: Out of memory\n"
    ),
    "/addons/core_mosquitto/logs": (
        "2026-10-20 13:54:30.000+02:00 homeassistant addon_core_mosquitto[1]: Exiting\n"
    ),
}


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


@pytest.fixture
def send_command(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> AsyncMock:
    """Mock the Supervisor log requests and freeze the time after the logs."""

    async def _send_command(command: str, **kwargs: object) -> str:
        if command not in LOGS:
            raise HassioAPIError
        return LOGS[command]

    mock = AsyncMock(side_effect=_send_command)
    hass.data[DATA_COMPONENT] = Mock(send_command=mock)
    freezer.move_to("2026-10-20 12:00:00+00:00")
    return mock


def _app(slug: str, name: str) -> Mock:
    """Return an installed app."""
    app = Mock(slug=slug)
    app.name = name
    return app


async def test_async_get_tools(
    hass: HomeAssistant, llm_context: llm.LLMContext, snapshot: SnapshotAssertion
) -> None:
    """Test the logs tool lists the installed apps as sources."""
    hass.data[DATA_ADDONS_LIST] = [_app("core_mosquitto", "Mosquitto broker")]

    assert async_get_tools(hass, llm_context, llm.LLM_API_ASSIST) is None
    tools = async_get_tools(hass, llm_context, llm.LLM_API_HOME_ASSISTANT)

    assert tools is not None
    assert [tool.name for tool in tools.tools] == ["hassio__get_logs"]
    assert probatio.to_openapi(tools.tools[0].parameters) == snapshot


async def test_get_logs_default(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    send_command: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the core and Supervisor logs are merged by default."""
    tool = SupervisorGetLogsTool({})

    result = await tool.async_call(hass, llm.ToolInput(tool.name, {}), llm_context)

    assert result == snapshot
    assert send_command.mock_calls == [
        call(
            f"/{source}/logs",
            method="get",
            return_text=True,
            params={"format": "plain", "no_colors": ""},
            range_header="realtime=1792496700.000000:1792497601:2000",
        )
        for source in ("core", "supervisor")
    ]


@pytest.mark.parametrize(
    ("tool_args", "expected_range"),
    [
        pytest.param(
            {
                "start_time": "2026-10-20T02:45:00+02:00",
                "end_time": "2026-10-20T03:00:00+02:00",
            },
            "realtime=1792457100.000000:1792458001:2000",
            id="whole_seconds",
        ),
        pytest.param(
            {
                "start_time": "2026-10-20T02:45:00.500+02:00",
                "end_time": "2026-10-20T03:00:00.500+02:00",
            },
            "realtime=1792457100.500000:1792458001:2000",
            id="fractions",
        ),
    ],
)
async def test_get_logs_time_window(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    send_command: AsyncMock,
    tool_args: dict[str, str],
    expected_range: str,
) -> None:
    """Test the journal returns the oldest lines in the time window."""
    tool = SupervisorGetLogsTool({})

    await tool.async_call(
        hass,
        llm.ToolInput(tool.name, {"source": ["host"], **tool_args}),
        llm_context,
    )

    assert send_command.mock_calls[0].kwargs["range_header"] == expected_range


async def test_get_logs_host_and_app(
    hass: HomeAssistant, llm_context: llm.LLMContext, send_command: AsyncMock
) -> None:
    """Test reading the host and app logs in the verbose format."""
    tool = SupervisorGetLogsTool({"core_mosquitto": "Mosquitto broker"})

    result = await tool.async_call(
        hass,
        llm.ToolInput(tool.name, {"source": ["host", "app:core_mosquitto"]}),
        llm_context,
    )

    assert [record["source"] for record in result.data["records"]] == [
        "host",
        "app:core_mosquitto",
    ]
    assert [
        (command, kwargs["params"]["format"])
        for _, (command,), kwargs in send_command.mock_calls
    ] == [
        ("/host/logs", "verbose"),
        ("/addons/core_mosquitto/logs", "verbose"),
    ]


async def test_get_logs_source_error(
    hass: HomeAssistant, llm_context: llm.LLMContext, send_command: AsyncMock
) -> None:
    """Test a source that cannot be read does not hide the other sources."""
    tool = SupervisorGetLogsTool({})

    result = await tool.async_call(
        hass, llm.ToolInput(tool.name, {"source": ["core", "dns"]}), llm_context
    )

    assert len(result.data["records"]) == 2
    assert result.data["errors"] == {"dns": "Could not read the dns log"}


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(["app:core_ssh"], id="app_not_installed"),
        pytest.param(["cli"], id="unknown_source"),
        pytest.param([], id="empty"),
        pytest.param(["../supervisor"], id="path_traversal"),
        pytest.param(["app:../../supervisor"], id="app_path_traversal"),
        pytest.param(["app:core_mosquitto/../../host"], id="app_suffix"),
        pytest.param(["core/logs?lines=1"], id="query"),
        pytest.param(["core", "../host"], id="valid_and_invalid"),
    ],
)
async def test_get_logs_invalid_source(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    send_command: AsyncMock,
    source: list[str],
) -> None:
    """Test only available sources are accepted, so no request is sent."""
    tool = SupervisorGetLogsTool({"core_mosquitto": "Mosquitto broker"})

    with pytest.raises(probatio.Invalid):
        await tool.async_call(
            hass, llm.ToolInput(tool.name, {"source": source}), llm_context
        )

    send_command.assert_not_called()


def _microseconds(time: str) -> int:
    """Return a time on 2026-10-20 in microseconds since the epoch."""
    return (
        datetime.fromisoformat(f"2026-10-20 {time}+02:00")
        - datetime(1970, 1, 1, tzinfo=UTC)
    ) // timedelta(microseconds=1)


def _mock_journal(hass: HomeAssistant, journal: list[tuple[str, str]]) -> None:
    """Mock the Supervisor with core lines by the time the journal received them."""

    async def _send_command(
        command: str, *, range_header: str, **kwargs: object
    ) -> str:
        start, end, lines = range_header.removeprefix("realtime=").split(":")
        return "\n".join(
            [
                "2026-10-20 {}+02:00 INFO (MainThread) [core] {}".format(
                    *line.split(" ", 1)
                )
                for received, line in journal
                if int(start.replace(".", ""))
                <= _microseconds(received)
                <= int(end) * 1_000_000
            ][: int(lines)]
        )

    hass.data[DATA_COMPONENT] = Mock(send_command=AsyncMock(side_effect=_send_command))


async def test_get_logs_received_after_end_time(
    hass: HomeAssistant, llm_context: llm.LLMContext, freezer: FrozenDateTimeFactory
) -> None:
    """Test a record at the end time that the journal received later is read."""
    freezer.move_to("2026-10-20 12:00:00+00:00")
    _mock_journal(hass, [("13:55:00.002", "13:55:00.000 At the end")])
    tool = SupervisorGetLogsTool({})

    result = await tool.async_call(
        hass,
        llm.ToolInput(
            tool.name, {"source": ["core"], "end_time": "2026-10-20T13:55:00+02:00"}
        ),
        llm_context,
    )

    assert [record["message"] for record in result.data["records"]] == [
        "INFO (MainThread) [core] At the end"
    ]


@pytest.mark.parametrize(
    ("journal", "pages"),
    [
        pytest.param(
            [
                ("13:50:00.100", "13:50:00.100 First"),
                ("13:50:00.200", "13:50:00.200 Second"),
                ("13:50:00.300", "13:50:00.300 Third"),
            ],
            [
                (["First"], "2026-10-20T04:50:00.101-07:00"),
                (["Second"], "2026-10-20T04:50:00.201-07:00"),
                (["Third"], None),
            ],
            id="busy_second",
        ),
        pytest.param(
            [
                ("13:50:00.000", "13:50:00.000 First"),
                ("13:50:01.000", "13:50:01.000 Third"),
                # Created before the record above, but received after it
                ("13:50:01.010", "13:50:00.950 Second"),
                ("13:50:02.000", "13:50:02.000 Fourth"),
            ],
            [
                (["First"], "2026-10-20T04:50:00.900-07:00"),
                (["Second"], "2026-10-20T04:50:00.951-07:00"),
                (["Third"], "2026-10-20T04:50:01.001-07:00"),
                (["Fourth"], "2026-10-20T04:50:02.001-07:00"),
                ([], None),
            ],
            id="received_out_of_order",
        ),
    ],
)
async def test_get_logs_pages(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    freezer: FrozenDateTimeFactory,
    journal: list[tuple[str, str]],
    pages: list[tuple[list[str], str | None]],
) -> None:
    """Test following next_start_time returns every record once."""
    freezer.move_to("2026-10-20 12:00:00+00:00")
    _mock_journal(hass, journal)
    tool = SupervisorGetLogsTool({})
    start_time = "2026-10-20T13:45:00+02:00"

    with patch("homeassistant.components.system_log.llm.LOG_QUERY_READ_LINES", 2):
        for expected_messages, expected_next_start_time in pages:
            result = await tool.async_call(
                hass,
                llm.ToolInput(
                    tool.name, {"source": ["core"], "start_time": start_time}
                ),
                llm_context,
            )
            assert [record["message"] for record in result.data["records"]] == [
                f"INFO (MainThread) [core] {message}" for message in expected_messages
            ]
            assert result.data.get("next_start_time") == expected_next_start_time
            start_time = expected_next_start_time
