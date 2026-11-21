"""Tests for history LLM tools."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from pytest_homeassistant.common import MockUser
from pytest_homeassistant.components.recorder.common import async_wait_recording_done
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import history
from homeassistant.components.history import llm as history_llm
from homeassistant.components.history.llm import (
    GetHistoryTool,
    SearchStatisticsTool,
    async_get_tools,
)
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.db_schema import StatisticsShortTerm
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_import_statistics,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType

ENTITY_ID = "sensor.temperature"
ENERGY_ENTITY_ID = "sensor.energy"
OTHER_ENTITY_ID = "sensor.humidity"
POWER_ENTITY_ID = "sensor.power"
EXTERNAL_STATISTIC_ID = "opower:electricity"


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
    external_metadata: StatisticMetaData = {
        "mean_type": StatisticMeanType.NONE,
        "has_sum": True,
        "name": "Electricity usage",
        "source": "opower",
        "statistic_id": EXTERNAL_STATISTIC_ID,
        "unit_class": "energy",
        "unit_of_measurement": "kWh",
    }
    async_add_external_statistics(
        hass,
        external_metadata,
        [
            StatisticData(start=start, state=hour, sum=hour)
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
        "history__get_history",
        "history__search_statistics",
    ]
    assert home_assistant_tools.prompt is None


def test_parameters_openapi(snapshot: SnapshotAssertion) -> None:
    """Test that the tool schemas can be exported for LLM clients."""
    assert {
        tool.name: probatio.to_openapi(
            tool.parameters, custom_serializer=llm.selector_serializer
        )
        for tool in (GetHistoryTool(), SearchStatisticsTool())
    } == snapshot


@pytest.mark.parametrize(
    "tool_args",
    [
        pytest.param({}, id="missing_statistic_ids"),
        pytest.param({"statistic_ids": []}, id="empty_statistic_ids"),
        pytest.param({"statistic_ids": ["not_an_entity"]}, id="invalid_id"),
        pytest.param({"statistic_ids": ["opower:"]}, id="invalid_statistic_id"),
        pytest.param({"statistic_ids": [ENTITY_ID], "period": "year"}, id="period"),
        pytest.param({"statistic_ids": [ENTITY_ID], "unknown": True}, id="unknown"),
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
            {"start_time": "2026-02-30T10:00:00"},
            "Invalid start_time",
            id="impossible_date",
        ),
        pytest.param(
            {
                "start_time": "2026-10-12T10:00:00+00:00",
                "end_time": "2026-10-12T09:00:00+00:00",
            },
            "start_time must be before end_time",
            id="reversed",
        ),
        pytest.param(
            {"start_time": "2026-09-01T00:00:00Z", "period": "hour"},
            "The time span has more than 500 hour rows. Use a longer period or "
            "a shorter time span.",
            id="too_many_rows",
        ),
    ],
)
@pytest.mark.freeze_time("2026-10-12 12:00:00+00:00")
async def test_invalid_time_span(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    tool_args: JsonObjectType,
    error: str,
) -> None:
    """Test an invalid time span returns an error result."""
    tool = GetHistoryTool()
    result = await tool.async_call(
        hass,
        llm.ToolInput(tool.name, {"statistic_ids": [ENTITY_ID], **tool_args}),
        llm_context,
    )

    assert result == llm.ToolResult(data={"error": error}, error=True)


@pytest.mark.usefixtures("recorder_mock", "recorded_statistics")
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
            {
                "statistic_ids": [ENERGY_ENTITY_ID],
                "start_time": "2026-10-12T10:00:00Z",
                "period": "hour",
            },
        )
    )
    assert result == llm.ToolResult(
        data={
            "result": {
                "period": "hour",
                "statistics": {
                    ENERGY_ENTITY_ID: {
                        "unit": "kWh",
                        "csv": "start,change\n"
                        "2026-10-12T03:00:00-07:00,1.5\n"
                        "2026-10-12T04:00:00-07:00,1.5\n",
                    }
                },
            }
        }
    )


@pytest.mark.usefixtures("recorder_mock", "recorded_statistics")
@pytest.mark.parametrize(
    "tool_args",
    [
        pytest.param({}, id="defaults"),
        pytest.param(
            {"start_time": "2026-10-12T09:00:00Z"},
            id="auto_period_5minute_falls_back_to_hour",
        ),
        pytest.param(
            {"start_time": "2026-10-12T09:00:00Z", "period": "5minute"},
            id="period_5minute_no_fallback",
        ),
        pytest.param({"start_time": "2026-10-09T12:00:00Z"}, id="auto_period_day"),
        pytest.param(
            {
                "start_time": "2026-09-01T10:00:00Z",
                "end_time": "2026-09-01T11:00:00Z",
            },
            id="auto_period_no_short_term",
        ),
        pytest.param(
            {
                "start_time": "2026-10-12T01:00:00",
                "end_time": "2026-10-12T03:00:00",
                "period": "hour",
            },
            id="local_time_span",
        ),
        pytest.param(
            {"start_time": "2026-10-11T00:00:00", "period": "day"}, id="period_day"
        ),
        pytest.param(
            {
                "start_time": "2026-10-10T00:00:00",
                "end_time": "2026-10-11T00:00:00",
                "period": "day",
            },
            id="period_day_exclusive_end",
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
                "statistic_ids": [ENTITY_ID, ENERGY_ENTITY_ID, OTHER_ENTITY_ID],
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
                "csv": "start,mean,min,max\n2026-10-12T04:00:00-07:00,74.6,158,161.6\n",
            },
            id="converted",
        ),
        pytest.param(
            ENERGY_ENTITY_ID,
            "Wh",
            {
                "unit": "Wh",
                "csv": "start,change\n2026-10-12T04:00:00-07:00,1500\n",
            },
            id="converted_sum",
        ),
        pytest.param(
            ENERGY_ENTITY_ID,
            "GWh",
            {
                "unit": "GWh",
                "csv": "start,change\n2026-10-12T04:00:00-07:00,1.5e-06\n",
            },
            id="converted_small_value",
        ),
        pytest.param(
            ENERGY_ENTITY_ID,
            "W",
            {"unit": "kWh", "csv": "start,change\n2026-10-12T04:00:00-07:00,1.5\n"},
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
    """Test statistics are converted to the unit of the entity when possible."""
    hass.states.async_set(entity_id, "1", {"unit_of_measurement": unit})
    tool = GetHistoryTool()
    result = await tool.async_call(
        hass,
        llm.ToolInput(
            tool.name,
            {
                "statistic_ids": [entity_id],
                "start_time": "2026-10-12T04:00:00",
                "end_time": "2026-10-12T05:00:00",
                "period": "hour",
            },
        ),
        llm_context,
    )

    assert result.error is False
    assert result.data["result"]["statistics"] == {entity_id: expected}


@pytest.mark.usefixtures("recorder_mock", "recorded_statistics")
async def test_hourly_fallback_per_entity(
    hass: HomeAssistant, llm_context: llm.LLMContext, snapshot: SnapshotAssertion
) -> None:
    """Test only entities without 5minute rows fall back to hourly rows."""
    first_start = dt_util.parse_datetime("2026-10-12 11:30:00+00:00")
    assert first_start is not None
    power_metadata: StatisticMetaData = {
        "mean_type": StatisticMeanType.ARITHMETIC,
        "has_sum": False,
        "name": None,
        "source": "recorder",
        "statistic_id": POWER_ENTITY_ID,
        "unit_class": "power",
        "unit_of_measurement": "W",
    }
    get_instance(hass).async_import_statistics(
        power_metadata,
        [
            StatisticData(
                start=first_start + timedelta(minutes=5 * index),
                mean=100 + index,
                min=90 + index,
                max=110 + index,
            )
            for index in range(3)
        ],
        StatisticsShortTerm,
    )
    await async_wait_recording_done(hass)

    tool = GetHistoryTool()
    result = await tool.async_call(
        hass,
        llm.ToolInput(
            tool.name,
            {
                "statistic_ids": [POWER_ENTITY_ID, ENERGY_ENTITY_ID],
                "start_time": "2026-10-12T10:00:00Z",
            },
        ),
        llm_context,
    )

    assert result.error is False
    assert result.data == snapshot


@pytest.mark.usefixtures("recorder_mock", "recorded_statistics")
async def test_get_external_statistics(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test getting a statistic without an entity."""
    tool = GetHistoryTool()
    result = await tool.async_call(
        hass,
        llm.ToolInput(
            tool.name,
            {
                "statistic_ids": [EXTERNAL_STATISTIC_ID],
                "start_time": "2026-10-12T10:00:00Z",
                "period": "hour",
            },
        ),
        llm_context,
    )

    assert result == llm.ToolResult(
        data={
            "result": {
                "period": "hour",
                "statistics": {
                    EXTERNAL_STATISTIC_ID: {
                        "unit": "kWh",
                        "csv": "start,change\n"
                        "2026-10-12T03:00:00-07:00,1\n"
                        "2026-10-12T04:00:00-07:00,1\n",
                    }
                },
            }
        }
    )


@pytest.mark.usefixtures("recorder_mock", "recorded_statistics")
@pytest.mark.parametrize(
    ("tool_args", "expected_ids"),
    [
        pytest.param(
            {}, [EXTERNAL_STATISTIC_ID, ENERGY_ENTITY_ID, ENTITY_ID], id="all"
        ),
        pytest.param(
            {"unit_class": "energy"},
            [EXTERNAL_STATISTIC_ID, ENERGY_ENTITY_ID],
            id="unit_class",
        ),
        pytest.param({"statistic_type": "mean"}, [ENTITY_ID], id="statistic_type"),
        pytest.param(
            {"query": "ELECTRICITY usage"}, [EXTERNAL_STATISTIC_ID], id="query_name"
        ),
        pytest.param({"query": "living room"}, [ENTITY_ID], id="query_entity_name"),
        pytest.param({"query": "sensor.energy"}, [ENERGY_ENTITY_ID], id="query_id"),
        pytest.param({"unit_class": "power"}, [], id="no_match"),
    ],
)
async def test_search_statistics(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    tool_args: JsonObjectType,
    expected_ids: list[str],
) -> None:
    """Test searching the statistics."""
    hass.states.async_set(ENTITY_ID, "21", {"friendly_name": "Living room temperature"})
    tool = SearchStatisticsTool()
    result = await tool.async_call(
        hass, llm.ToolInput(tool.name, tool_args), llm_context
    )

    assert result.error is False
    assert [item["statistic_id"] for item in result.data["statistics"]] == (
        expected_ids
    )
    assert result.data["total"] == len(expected_ids)
    assert "next_offset" not in result.data


@pytest.mark.usefixtures("recorder_mock", "recorded_statistics")
async def test_search_statistics_details(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test the details of the found statistics."""
    hass.states.async_set(
        ENTITY_ID,
        "70",
        {"friendly_name": "Living room temperature", "unit_of_measurement": "°F"},
    )
    tool = SearchStatisticsTool()
    result = await tool.async_call(hass, llm.ToolInput(tool.name, {}), llm_context)

    assert result.data["statistics"] == [
        {
            "statistic_id": EXTERNAL_STATISTIC_ID,
            "name": "Electricity usage",
            "source": "opower",
            "unit": "kWh",
            "unit_class": "energy",
            "has_sum": True,
            "has_mean": False,
        },
        {
            "statistic_id": ENERGY_ENTITY_ID,
            "name": None,
            "source": "recorder",
            "unit": "kWh",
            "unit_class": "energy",
            "has_sum": True,
            "has_mean": False,
        },
        {
            "statistic_id": ENTITY_ID,
            "name": "Living room temperature",
            "source": "recorder",
            "unit": "°F",
            "unit_class": "temperature",
            "has_sum": False,
            "has_mean": True,
        },
    ]


@pytest.mark.usefixtures("recorder_mock", "recorded_statistics")
async def test_search_statistics_pagination(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test paging through the statistics with offset and next_offset."""
    monkeypatch.setattr(history_llm, "_SEARCH_LIMIT", 2)
    tool = SearchStatisticsTool()

    first = await tool.async_call(hass, llm.ToolInput(tool.name, {}), llm_context)
    assert [item["statistic_id"] for item in first.data["statistics"]] == [
        EXTERNAL_STATISTIC_ID,
        ENERGY_ENTITY_ID,
    ]
    assert first.data["total"] == 3
    assert first.data["next_offset"] == 2

    second = await tool.async_call(
        hass, llm.ToolInput(tool.name, {"offset": 2}), llm_context
    )
    assert [item["statistic_id"] for item in second.data["statistics"]] == [ENTITY_ID]
    assert "next_offset" not in second.data


@pytest.mark.parametrize(
    "tool_args",
    [
        pytest.param({"unit_class": "dollars"}, id="unit_class"),
        pytest.param({"statistic_type": "max"}, id="statistic_type"),
        pytest.param({"query": ""}, id="empty_query"),
        pytest.param({"offset": -1}, id="offset"),
    ],
)
async def test_search_statistics_invalid_parameters(
    hass: HomeAssistant, llm_context: llm.LLMContext, tool_args: JsonObjectType
) -> None:
    """Test invalid search parameters are rejected."""
    tool = SearchStatisticsTool()
    with pytest.raises(probatio.Invalid):
        await tool.async_call(hass, llm.ToolInput(tool.name, tool_args), llm_context)
