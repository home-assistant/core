"""Tests for history LLM tools."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import history
from homeassistant.components.history.llm import GetHistoryTool, async_get_tools
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType

from tests.common import MockUser
from tests.components.recorder.common import async_wait_recording_done

ENTITY_ID = "sensor.temperature"
OTHER_ENTITY_ID = "sensor.humidity"


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
async def recorded_states(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Record a series of states, one hour apart, ending at 2026-10-12 12:00 UTC."""
    freezer.move_to("2026-10-12 08:00:00+00:00")
    assert await async_setup_component(hass, history.DOMAIN, {})
    hass.states.async_set(OTHER_ENTITY_ID, "45")
    for value in ("18.0", "19.5", "21.0", "20.5"):
        hass.states.async_set(
            ENTITY_ID, value, {"unit_of_measurement": "°C", "friendly_name": "Temp"}
        )
        await async_wait_recording_done(hass)
        freezer.tick(timedelta(hours=1))


async def test_async_get_tools(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test async_get_tools returns tools only for Home Assistant API."""
    assert async_get_tools(hass, llm_context, llm.LLM_API_ASSIST) is None

    home_assistant_tools = async_get_tools(
        hass, llm_context, llm.LLM_API_HOME_ASSISTANT
    )
    assert home_assistant_tools is not None
    assert [tool.name for tool in home_assistant_tools.tools] == [
        "history__get_history"
    ]
    assert home_assistant_tools.prompt is None


def test_parameters_openapi(snapshot: SnapshotAssertion) -> None:
    """Test that the tool schema can be exported for LLM clients."""
    assert (
        probatio.to_openapi(
            GetHistoryTool.parameters, custom_serializer=llm.selector_serializer
        )
        == snapshot
    )


@pytest.mark.parametrize(
    "tool_args",
    [
        pytest.param({}, id="missing_entity_ids"),
        pytest.param({"entity_ids": []}, id="empty_entity_ids"),
        pytest.param({"entity_ids": ["not_an_entity"]}, id="invalid_entity_id"),
        pytest.param({"entity_ids": [ENTITY_ID], "limit": 0}, id="limit_too_low"),
        pytest.param({"entity_ids": [ENTITY_ID], "limit": 1001}, id="limit_too_high"),
        pytest.param(
            {"entity_ids": [ENTITY_ID], "include_attributes": "invalid"},
            id="invalid_boolean",
        ),
        pytest.param({"entity_ids": [ENTITY_ID], "unknown": True}, id="unknown"),
    ],
)
async def test_invalid_parameters(
    hass: HomeAssistant, llm_context: llm.LLMContext, tool_args: JsonObjectType
) -> None:
    """Test invalid arguments are rejected by the Probatio schema."""
    tool = GetHistoryTool()

    with pytest.raises(probatio.Invalid):
        await tool.async_call(hass, llm.ToolInput(tool.name, tool_args), llm_context)


@pytest.mark.parametrize(
    ("tool_args", "error"),
    [
        pytest.param({"start_time": "yesterday"}, "Invalid start_time", id="start"),
        pytest.param({"end_time": "now"}, "Invalid end_time", id="end"),
        pytest.param(
            {
                "start_time": "2026-10-12T10:00:00+00:00",
                "end_time": "2026-10-12T09:00:00+00:00",
            },
            "start_time must be before end_time",
            id="reversed",
        ),
    ],
)
async def test_invalid_period(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    tool_args: JsonObjectType,
    error: str,
) -> None:
    """Test an invalid period returns an error result."""
    tool = GetHistoryTool()
    result = await tool.async_call(
        hass,
        llm.ToolInput(tool.name, {"entity_ids": [ENTITY_ID], **tool_args}),
        llm_context,
    )

    assert result == llm.ToolResult(data={"error": error}, error=True)


@pytest.mark.usefixtures("recorder_mock", "recorded_states")
async def test_call_through_api(
    hass: HomeAssistant, hass_admin_user: MockUser, llm_context: llm.LLMContext
) -> None:
    """Test tool discovery and results through the Home Assistant API."""
    assert await async_setup_component(hass, "llm", {})
    llm_context.context = Context(user_id=hass_admin_user.id)

    api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)
    tool = next(tool for tool in api.tools if tool.name == "history__get_history")
    assert tool.integration == history.DOMAIN
    assert tool.annotations == llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    result = await api.async_call_tool(
        llm.ToolInput(tool.name, {"entity_ids": [OTHER_ENTITY_ID]})
    )
    assert result == llm.ToolResult(
        data={
            "result": {
                OTHER_ENTITY_ID: {
                    "total": 1,
                    "states": [
                        {
                            "state": "45",
                            "last_changed": "2026-10-12T01:00:00-07:00",
                        }
                    ],
                }
            }
        }
    )


@pytest.mark.usefixtures("recorder_mock", "recorded_states")
@pytest.mark.parametrize(
    "tool_args",
    [
        pytest.param({}, id="defaults"),
        pytest.param({"limit": 2}, id="limit"),
        pytest.param({"include_attributes": True}, id="include_attributes"),
        pytest.param(
            {
                "start_time": "2026-10-12T02:30:00",
                "end_time": "2026-10-12T03:30:00",
            },
            id="local_period",
        ),
        pytest.param(
            {"start_time": "2026-10-12T10:30:00+00:00"}, id="start_time_with_offset"
        ),
        pytest.param({"end_time": "2026-10-12T09:30:00Z"}, id="end_time_only"),
        pytest.param(
            {"end_time": "2026-10-12T07:00:00+00:00"}, id="before_first_state"
        ),
    ],
)
async def test_get_history(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    snapshot: SnapshotAssertion,
    tool_args: JsonObjectType,
) -> None:
    """Test getting the history of entities."""
    assert dt_util.utcnow().isoformat() == "2026-10-12T12:00:00+00:00"
    tool = GetHistoryTool()
    result = await tool.async_call(
        hass,
        llm.ToolInput(
            tool.name, {"entity_ids": [ENTITY_ID, "sensor.unknown"], **tool_args}
        ),
        llm_context,
    )

    assert result.error is False
    assert result.data == snapshot
