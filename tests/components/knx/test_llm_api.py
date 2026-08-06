"""Tests for the KNX LLM API."""

from unittest.mock import AsyncMock, Mock

from knx_telegram_store.mcp import QueryTelegramsResult
import pytest
import voluptuous as vol

from homeassistant.components.knx import llm_api
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm

from .conftest import KNXTestKit

from tests.common import MockUser

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


def _llm_context(user_id: str | None = None) -> llm.LLMContext:
    return llm.LLMContext(
        platform="knx",
        context=Context(user_id=user_id),
        language="en",
        assistant="conversation",
        device_id=None,
    )


def _tool(tools: list[llm.Tool], name: str) -> llm.Tool:
    return next(tool for tool in tools if tool.name == name)


async def test_llm_api_registered_after_setup(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Setup registers the API; bus tools are only exposed to admins."""
    await knx.setup_integration()

    admin_instance = await llm.async_get_api(
        hass, llm_api.LLM_API_ID, _llm_context(hass_admin_user.id)
    )
    admin_tools = {tool.name for tool in admin_instance.tools}
    assert "query_telegrams" in admin_tools
    assert admin_tools >= _BUS_TOOLS

    # Non-admin (and anonymous) users get read-only tools without the bus tools.
    for user_id in (hass_read_only_user.id, None):
        instance = await llm.async_get_api(
            hass, llm_api.LLM_API_ID, _llm_context(user_id)
        )
        tool_names = {tool.name for tool in instance.tools}
        assert "query_telegrams" in tool_names
        assert tool_names.isdisjoint(_BUS_TOOLS)

    await hass.config_entries.async_unload(knx.mock_config_entry.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(HomeAssistantError, match="not found"):
        await llm.async_get_api(hass, llm_api.LLM_API_ID, _llm_context())


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


@pytest.mark.parametrize(
    ("value", "expected", "expected_type"),
    [
        (True, True, bool),
        (5, 5, int),
        (5.5, 5.5, float),  # not truncated to 5 by the int branch of the union
        (5.0, 5, int),  # losslessly representable as int
        ("on", "on", str),
        ([1, 2], [1, 2], list),
    ],
)
def test_schema_union_preserves_numeric_types(
    value: object, expected: object, expected_type: type
) -> None:
    """A `bool | int | float | ...` union field keeps each type distinct."""
    tool = _tool(
        llm_api._build_tools(None, include_bus_tools=True), "send_group_value_write"
    )
    result = tool.parameters({"group_address": "1/2/3", "value": value})
    assert result["value"] == expected
    assert type(result["value"]) is expected_type


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ({"a": 1}, {"a": 1}),  # mapping passes through unchanged
        (5, {"result": 5}),  # bare scalar is wrapped
        ("text", {"result": "text"}),
        (None, {"result": None}),
    ],
)
def test_serialize_always_returns_an_object(result: object, expected: dict) -> None:
    """`_serialize` wraps non-dataclass, non-list, non-dict results."""
    assert llm_api._serialize(result) == expected


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
    with pytest.raises(
        HomeAssistantError, match="llm_telegram_store_unavailable"
    ) as err:
        await tool.async_call(
            hass,
            llm.ToolInput(tool_name="get_store_stats", tool_args={}),
            _llm_context(),
        )
    assert err.value.translation_key == "llm_telegram_store_unavailable"


async def test_project_tool_without_project_raises(hass: HomeAssistant) -> None:
    """A project tool errors clearly when no ETS project is loaded."""
    tool = _tool(
        llm_api._build_tools(_mock_knx(project=None), include_bus_tools=False),
        "get_project_info",
    )
    with pytest.raises(HomeAssistantError, match="llm_no_project_loaded") as err:
        await tool.async_call(
            hass,
            llm.ToolInput(tool_name="get_project_info", tool_args={}),
            _llm_context(),
        )
    assert err.value.translation_key == "llm_no_project_loaded"
