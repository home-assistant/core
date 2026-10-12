"""Tests for history LLM tools."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import history
from homeassistant.components.history.llm import GetHistoryTool, async_get_tools
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType

from tests.common import MockUser
from tests.components.recorder.common import async_wait_recording_done

ENTITY_ID = "sensor.temperature"
ENERGY_ENTITY_ID = "sensor.energy"
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
    """Record a series of states, one hour apart, starting at 2026-10-12 08:00 UTC."""
    # Microseconds check that times are returned with second precision.
    freezer.move_to("2026-10-12 08:00:00.123456+00:00")
    assert await async_setup_component(hass, history.DOMAIN, {})
    hass.states.async_set(OTHER_ENTITY_ID, "45")
    for value in ("18.0", "19.5", "21.0", "20.5"):
        hass.states.async_set(
            ENTITY_ID, value, {"unit_of_measurement": "°C", "friendly_name": "Temp"}
        )
        await async_wait_recording_done(hass)
        freezer.tick(timedelta(hours=1))


@pytest.fixture
async def recorded_statistics(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Record 72 hours of statistics, ending at 2026-10-12 12:00 UTC."""
    freezer.move_to("2026-10-12 12:00:00+00:00")
    assert await async_setup_component(hass, history.DOMAIN, {})
    first_start = dt_util.parse_datetime("2026-10-09 12:00:00+00:00")
    assert first_start is not None
    starts = [first_start + timedelta(hours=hour) for hour in range(72)]
    temperature_metadata: StatisticMetaData = {
        "mean_type": StatisticMeanType.ARITHMETIC,
        "has_sum": False,
        "name": None,
        "source": "recorder",
        "statistic_id": ENTITY_ID,
        "unit_class": "temperature",
        "unit_of_measurement": "°C",
    }
    async_import_statistics(
        hass,
        temperature_metadata,
        [
            StatisticData(start=start, mean=hour / 3, min=hour - 1, max=hour + 1)
            for hour, start in enumerate(starts)
        ],
    )
    energy_metadata: StatisticMetaData = {
        "mean_type": StatisticMeanType.NONE,
        "has_sum": True,
        "name": None,
        "source": "recorder",
        "statistic_id": ENERGY_ENTITY_ID,
        "unit_class": "energy",
        "unit_of_measurement": "kWh",
    }
    async_import_statistics(
        hass,
        energy_metadata,
        [
            StatisticData(start=start, state=hour * 1.5, sum=hour * 1.5)
            for hour, start in enumerate(starts)
        ],
    )
    await async_wait_recording_done(hass)


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
            {"entity_ids": [ENTITY_ID], "include_full_attributes": "invalid"},
            id="invalid_boolean",
        ),
        pytest.param({"entity_ids": [ENTITY_ID], "source": "raw"}, id="source"),
        pytest.param({"entity_ids": [ENTITY_ID], "period": "year"}, id="period"),
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
        llm.ToolInput(
            tool.name,
            {"entity_ids": [OTHER_ENTITY_ID], "source": "state_changes"},
        )
    )
    assert result == llm.ToolResult(
        data={
            "result": {
                "source": "state_changes",
                "entities": {
                    OTHER_ENTITY_ID: {
                        "csv": "time,state\n2026-10-12T01:00:00-07:00,45\n"
                    }
                },
            }
        }
    )


@pytest.mark.usefixtures("recorder_mock", "recorded_states")
@pytest.mark.parametrize(
    "tool_args",
    [
        pytest.param({}, id="defaults"),
        pytest.param({"limit": 2}, id="limit"),
        pytest.param({"include_full_attributes": True}, id="include_full_attributes"),
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
async def test_get_state_changes(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    snapshot: SnapshotAssertion,
    tool_args: JsonObjectType,
) -> None:
    """Test getting the state changes of entities."""
    assert dt_util.utcnow().isoformat() == "2026-10-12T12:00:00.123456+00:00"
    tool = GetHistoryTool()
    result = await tool.async_call(
        hass,
        llm.ToolInput(
            tool.name,
            {
                "entity_ids": [ENTITY_ID, "sensor.unknown"],
                "source": "state_changes",
                **tool_args,
            },
        ),
        llm_context,
    )

    assert result.error is False
    assert result.data == snapshot


@pytest.mark.usefixtures("recorder_mock", "recorded_statistics")
@pytest.mark.parametrize(
    "tool_args",
    [
        pytest.param({}, id="defaults"),
        pytest.param({"limit": 2}, id="limit"),
        pytest.param({"start_time": "2026-10-09T12:00:00Z"}, id="auto_period_day"),
        pytest.param(
            {"start_time": "2026-10-12T09:00:00Z", "period": "5minute"},
            id="no_short_term_statistics",
        ),
        pytest.param(
            {"start_time": "2026-10-11T00:00:00", "period": "day"}, id="period_day"
        ),
    ],
)
async def test_get_statistics(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    snapshot: SnapshotAssertion,
    tool_args: JsonObjectType,
) -> None:
    """Test getting the statistics of entities."""
    tool = GetHistoryTool()
    result = await tool.async_call(
        hass,
        llm.ToolInput(
            tool.name,
            {
                "entity_ids": [ENTITY_ID, ENERGY_ENTITY_ID, OTHER_ENTITY_ID],
                **tool_args,
            },
        ),
        llm_context,
    )

    assert result.error is False
    assert result.data == snapshot


@pytest.mark.usefixtures("recorder_mock", "recorded_statistics")
@pytest.mark.parametrize(
    ("entity_id", "unit", "expected"),
    [
        pytest.param(
            ENTITY_ID,
            "°F",
            {
                "unit": "°F",
                "total": 24,
                "csv": "start,mean,min,max\n2026-10-12T04:00:00-07:00,74.6,158.0,161.6\n",
            },
            id="converted",
        ),
        pytest.param(
            ENERGY_ENTITY_ID,
            "Wh",
            {
                "unit": "Wh",
                "total": 24,
                "csv": "start,change\n2026-10-12T04:00:00-07:00,1500.0\n",
            },
            id="converted_sum",
        ),
        pytest.param(
            ENERGY_ENTITY_ID,
            "W",
            {
                "error": "Statistics are recorded in kWh, which cannot be "
                "converted to the unit of the entity. Use source "
                "'state_changes' instead."
            },
            id="not_convertible",
        ),
    ],
)
async def test_statistics_state_unit(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    entity_id: str,
    unit: str,
    expected: JsonObjectType,
) -> None:
    """Test statistics are reported in the unit of the entity's state."""
    hass.states.async_set(entity_id, "1", {"unit_of_measurement": unit})
    tool = GetHistoryTool()
    result = await tool.async_call(
        hass,
        llm.ToolInput(tool.name, {"entity_ids": [entity_id], "limit": 1}),
        llm_context,
    )

    assert result.error is False
    assert result.data["result"]["entities"] == {entity_id: expected}


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    ("include_full_attributes", "expected_csv"),
    [
        pytest.param(
            False,
            "time,state,current_position\n"
            "2026-10-12T01:00:00-07:00,open,30\n"
            "2026-10-12T02:00:00-07:00,open,80\n"
            "2026-10-12T04:00:00-07:00,closed,0\n",
            id="significant_attributes",
        ),
        pytest.param(
            True,
            "time,state,current_position,attributes\n"
            '2026-10-12T01:00:00-07:00,open,30,"{""current_position"":30}"\n'
            '2026-10-12T02:00:00-07:00,open,80,"{""current_position"":80}"\n'
            '2026-10-12T04:00:00-07:00,closed,0,"{""current_position"":0,""friendly_name"":""Garage""}"\n',
            id="include_full_attributes",
        ),
    ],
)
async def test_state_changes_significant_attributes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    llm_context: llm.LLMContext,
    include_full_attributes: bool,
    expected_csv: str,
) -> None:
    """Test significant attributes are returned as columns for state changes."""
    freezer.move_to("2026-10-12 08:00:00+00:00")
    assert await async_setup_component(hass, history.DOMAIN, {})
    for state, attributes in (
        ("open", {"current_position": 30}),
        # Only a significant attribute changes.
        ("open", {"current_position": 80}),
        # Only an insignificant attribute changes.
        ("open", {"current_position": 80, "friendly_name": "Garage"}),
        ("closed", {"current_position": 0, "friendly_name": "Garage"}),
    ):
        hass.states.async_set("cover.garage", state, attributes)
        await async_wait_recording_done(hass)
        freezer.tick(timedelta(hours=1))

    tool = GetHistoryTool()
    result = await tool.async_call(
        hass,
        llm.ToolInput(
            tool.name,
            {
                "entity_ids": ["cover.garage"],
                "source": "state_changes",
                "include_full_attributes": include_full_attributes,
            },
        ),
        llm_context,
    )

    assert result == llm.ToolResult(
        data={
            "result": {
                "source": "state_changes",
                "entities": {"cover.garage": {"csv": expected_csv}},
            }
        }
    )


@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize(
    ("include_full_attributes", "expected_csv"),
    [
        pytest.param(
            False,
            "time,state\n2026-10-12T01:00:00-07:00,playing\n2026-10-12T03:00:00-07:00,paused\n",
            id="state_only",
        ),
        pytest.param(
            True,
            "time,state,attributes\n"
            '2026-10-12T01:00:00-07:00,playing,"{""media_title"":""Song 1""}"\n'
            '2026-10-12T03:00:00-07:00,paused,"{""media_title"":""Song 2""}"\n',
            id="include_full_attributes",
        ),
    ],
)
async def test_state_changes_media_player(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    llm_context: llm.LLMContext,
    include_full_attributes: bool,
    expected_csv: str,
) -> None:
    """Test media player attributes are only returned when requested."""
    freezer.move_to("2026-10-12 08:00:00+00:00")
    assert await async_setup_component(hass, history.DOMAIN, {})
    for state, title in (
        ("playing", "Song 1"),
        ("playing", "Song 2"),
        ("paused", "Song 2"),
    ):
        hass.states.async_set("media_player.speaker", state, {"media_title": title})
        await async_wait_recording_done(hass)
        freezer.tick(timedelta(hours=1))

    tool = GetHistoryTool()
    result = await tool.async_call(
        hass,
        llm.ToolInput(
            tool.name,
            {
                "entity_ids": ["media_player.speaker"],
                "source": "state_changes",
                "include_full_attributes": include_full_attributes,
            },
        ),
        llm_context,
    )

    assert result.data["result"]["entities"] == {
        "media_player.speaker": {"csv": expected_csv}
    }
