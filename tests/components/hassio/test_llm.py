"""Tests for the Hass.io LLM tools."""

from unittest.mock import AsyncMock, Mock, call

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
            params={"lines": 2000, "format": "plain", "no_colors": ""},
        )
        for source in ("core", "supervisor")
    ]


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

    assert result.data["sources"] == {
        "core": {"matched": 2, "returned": 2},
        "dns": {"error": "Could not read the dns log"},
    }


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(["app:core_mosquitto"], id="app_not_installed"),
        pytest.param(["cli"], id="unknown_source"),
        pytest.param([], id="empty"),
    ],
)
async def test_get_logs_invalid_source(
    hass: HomeAssistant, llm_context: llm.LLMContext, source: list[str]
) -> None:
    """Test only available sources are accepted."""
    tool = SupervisorGetLogsTool({})

    with pytest.raises(probatio.Invalid):
        await tool.async_call(
            hass, llm.ToolInput(tool.name, {"source": source}), llm_context
        )
