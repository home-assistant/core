"""Tests for the KNX LLM API."""

from unittest.mock import AsyncMock, Mock

from knx_telegram_store.mcp import QueryTelegramsResult
import pytest
import voluptuous as vol

from homeassistant.components.knx import llm_api
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm

_BUS_TOOLS = {"read_group_value", "send_group_value_read", "send_group_value_write"}


def _mock_knx(
    *,
    store: object | None = None,
    project: dict | None = None,
    xknx: object | None = None,
) -> Mock:
    """A KNX module mock exposing the handles the tools use."""
    knx = Mock()
    knx.telegrams.store = store
    knx.project.get_knxproject = AsyncMock(return_value=project)
    knx.xknx = xknx
    return knx


def _llm_context() -> llm.LLMContext:
    return llm.LLMContext(
        platform="knx",
        context=Context(),
        language="en",
        assistant="conversation",
        device_id=None,
    )


def _tool(tools: list[llm.Tool], name: str) -> llm.Tool:
    return next(tool for tool in tools if tool.name == name)


def test_bus_tools_are_gated() -> None:
    """Bus tools are only present when explicitly enabled."""
    read_only = {
        tool.name for tool in llm_api._build_tools(None, include_bus_tools=False)
    }
    with_bus = {
        tool.name for tool in llm_api._build_tools(None, include_bus_tools=True)
    }

    assert read_only.isdisjoint(_BUS_TOOLS)
    assert with_bus >= _BUS_TOOLS
    assert with_bus - read_only == _BUS_TOOLS


def test_schema_from_dataclass_defaults_and_descriptions() -> None:
    """Optional fields carry defaults and their library metadata descriptions."""
    tool = _tool(llm_api._build_tools(None, include_bus_tools=False), "query_telegrams")

    descriptions = {
        marker.schema: marker.description for marker in tool.parameters.schema
    }
    assert descriptions["limit"] == "Maximum number of results to return."
    assert all(description for description in descriptions.values())

    # Omitted optional fields are filled with their dataclass defaults.
    result = tool.parameters({})
    assert result["limit"] == 100
    assert result["order_descending"] is True
    assert result["sources"] == []


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ({"main": "9"}, 9),  # string coerced to int
        ({"main": 9}, 9),
        ({}, None),  # nullable field defaults to None, not rejected
    ],
)
def test_schema_coercion_and_nullable(args: dict, expected: int | None) -> None:
    """Integer coercion works and nullable defaults are accepted."""
    tool = _tool(llm_api._build_tools(None, include_bus_tools=False), "list_dpts")
    assert tool.parameters(args)["main"] == expected


def test_schema_required_field_is_enforced() -> None:
    """A field without a default (ad-hoc arg) is required."""
    tool = _tool(llm_api._build_tools(None, include_bus_tools=False), "describe_dpt")
    with pytest.raises(vol.Invalid):
        tool.parameters({})


async def test_describe_dpt_tool_call(hass: HomeAssistant) -> None:
    """A DPT tool needs no KNX runtime state and returns a serialized result."""
    tool = _tool(
        llm_api._build_tools(_mock_knx(), include_bus_tools=False), "describe_dpt"
    )
    result = await tool.async_call(
        hass,
        llm.ToolInput(tool_name="describe_dpt", tool_args={"dpt": "9.001"}),
        _llm_context(),
    )
    assert result["found"] is True
    assert result["dpt"]["dpt"] == "9.001"
    assert result["dpt"]["unit"] == "°C"


async def test_query_telegrams_tool_call(hass: HomeAssistant) -> None:
    """The store tool passes a typed input to the library and serializes the result."""
    store = Mock()
    lib_result = QueryTelegramsResult(
        telegrams=[], total_count=0, offset=0, next_offset=None, limit_reached=False
    )
    knx = _mock_knx(store=store)

    with pytest.MonkeyPatch.context() as mp:
        query = AsyncMock(return_value=lib_result)
        # Patch before building the tool: the factory captures the function reference.
        mp.setattr(llm_api.kts_mcp, "query_telegrams", query)
        tool = _tool(
            llm_api._build_tools(knx, include_bus_tools=False), "query_telegrams"
        )
        result = await tool.async_call(
            hass,
            llm.ToolInput(tool_name="query_telegrams", tool_args={"limit": "5"}),
            _llm_context(),
        )

    assert query.await_args.args[0] is store
    assert query.await_args.args[1].limit == 5  # coerced from "5"
    assert result["total_count"] == 0


async def test_store_tool_without_store_raises(hass: HomeAssistant) -> None:
    """A store tool errors clearly when the telegram store is unavailable."""
    tool = _tool(
        llm_api._build_tools(_mock_knx(store=None), include_bus_tools=False),
        "get_store_stats",
    )
    with pytest.raises(HomeAssistantError, match="telegram store"):
        await tool.async_call(
            hass,
            llm.ToolInput(tool_name="get_store_stats", tool_args={}),
            _llm_context(),
        )


async def test_project_tool_without_project_raises(hass: HomeAssistant) -> None:
    """A project tool errors clearly when no ETS project is loaded."""
    tool = _tool(
        llm_api._build_tools(_mock_knx(project=None), include_bus_tools=False),
        "get_project_info",
    )
    with pytest.raises(HomeAssistantError, match="project"):
        await tool.async_call(
            hass,
            llm.ToolInput(tool_name="get_project_info", tool_args={}),
            _llm_context(),
        )
