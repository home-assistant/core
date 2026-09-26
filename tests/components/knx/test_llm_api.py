"""Tests for the KNX LLM API."""

from dataclasses import fields
from datetime import UTC, date, datetime, time
import json
from typing import Any
from unittest.mock import AsyncMock, Mock

from knx_telegram_store.mcp import (
    QueryTelegramsInput,
    QueryTelegramsResult,
    TelegramSummary,
)
import probatio
from probatio import to_openapi
import pytest
from xknx.dpt import DPTArray, DPTTime

from homeassistant.components.knx import llm_api
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm

from .conftest import KNXTestKit

from tests.common import MockUser

_BUS_TOOLS = {"read_group_value", "send_group_value_read", "send_group_value_write"}
# The complete set, asserted exactly: a subset check cannot notice a tool that
# silently stops being registered. `list_locations` is deliberately absent - it
# is the one library tool with no adapter-side bound, because nesting depth
# drives its size, and it needs depth/space_id in xknxproject first.
_EXPECTED_TOOLS = {
    "count_telegrams",
    "decode_payload",
    "describe_dpt",
    "describe_function",
    "describe_group_address",
    "encode_value",
    "get_connection_status",
    "get_last_values",
    "get_project_info",
    "get_store_capabilities",
    "get_store_stats",
    "get_topology",
    "list_communication_objects",
    "list_devices",
    "list_dpts",
    "list_functions",
    "list_group_addresses",
    "query_telegrams",
    *_BUS_TOOLS,
}


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


def _telegram_summary(destination: str) -> TelegramSummary:
    return TelegramSummary(
        timestamp="2026-08-27T12:00:00+00:00",
        source="1.1.1",
        destination=destination,
        telegramtype="GroupValueWrite",
        direction="Incoming",
        dpt=None,
        value=1,
        value_numeric=None,
        raw_data="01",
        source_name=None,
        destination_name=None,
    )


async def test_llm_api_registered_after_setup(
    hass: HomeAssistant, knx: KNXTestKit, hass_admin_user: MockUser
) -> None:
    """Setup registers the API with all tools; unload deregisters it."""
    await knx.setup_integration()

    instance = await llm.async_get_api(
        hass, llm_api.LLM_API_ID, _llm_context(hass_admin_user.id)
    )
    tool_names = {tool.name for tool in instance.tools}
    assert tool_names == _EXPECTED_TOOLS
    assert tool_names >= _BUS_TOOLS

    await hass.config_entries.async_unload(knx.mock_config_entry.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(HomeAssistantError, match="not found"):
        await llm.async_get_api(hass, llm_api.LLM_API_ID, _llm_context())


def test_schema_from_dataclass_defaults_and_descriptions() -> None:
    """Optional fields carry defaults and their library metadata descriptions.

    The libraries document parameters in `dataclasses.field` metadata, which
    probatio's `DataclassSchema` does not read, so `llm_api` carries them over.
    """
    tool = _tool(llm_api._build_tools(_mock_knx()), "query_telegrams")

    properties = to_openapi(tool.parameters)["properties"]
    # Compared against the library's own metadata rather than a copy of its
    # wording, which a library bump would otherwise break.
    limit_field = next(
        field for field in fields(QueryTelegramsInput) if field.name == "limit"
    )
    assert properties["limit"]["description"] == limit_field.metadata["description"]
    assert all("description" in prop for prop in properties.values())

    # Omitted optional fields are filled with their dataclass defaults.
    result = tool.parameters({})
    assert isinstance(result, QueryTelegramsInput)
    assert result.limit == 100
    assert result.order_descending is True
    assert result.sources == []


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        pytest.param({"main": 9}, 9, id="given"),
        pytest.param({}, None, id="nullable_default"),
    ],
)
def test_schema_nullable_field(args: dict[str, Any], expected: int | None) -> None:
    """A nullable field defaults to None instead of being rejected."""
    tool = _tool(llm_api._build_tools(_mock_knx()), "list_dpts")
    assert tool.parameters(args).main == expected


def test_schema_validates_types_without_coercing() -> None:
    """Probatio type-checks, so a stringified number is an error, not an int."""
    tool = _tool(llm_api._build_tools(_mock_knx()), "list_dpts")
    with pytest.raises(probatio.Invalid):
        tool.parameters({"main": "9"})


@pytest.mark.parametrize(
    ("value", "expected", "expected_type"),
    [
        (True, True, bool),
        (5, 5, int),
        (5.5, 5.5, float),
        ("on", "on", str),
        # A numeric-looking string stays text - DPT 16.000 sends exactly that.
        ("5", "5", str),
        ("21.5", "21.5", str),
        ([1, 2], [1, 2], list),
    ],
)
def test_schema_union_preserves_numeric_types(
    value: object, expected: object, expected_type: type
) -> None:
    """A `bool | int | float | ...` union field keeps each type distinct."""
    tool = _tool(
        llm_api._build_tools(_mock_knx()),
        "send_group_value_write",
    )
    result = tool.parameters({"group_address": "1/2/3", "value": value})
    assert result.value == expected
    assert type(result.value) is expected_type


@pytest.mark.parametrize(
    ("tool_name", "parameter", "expected"),
    [
        (
            "query_telegrams",
            "limit",
            {"type": "integer", "minimum": 1, "maximum": 1000},
        ),
        (
            "query_telegrams",
            "dpt_mains",
            {"type": "array", "items": {"type": "integer"}},
        ),
        ("list_dpts", "main", {"type": "integer", "nullable": True}),
        (
            "decode_payload",
            "payload",
            {
                "anyOf": [
                    {"type": "array", "items": {"type": "integer"}},
                    {"type": "integer"},
                ]
            },
        ),
    ],
)
def test_integer_parameters_are_typed_for_the_llm(
    tool_name: str, parameter: str, expected: dict[str, Any]
) -> None:
    """Integer fields must not be advertised to the model as strings."""
    tool = _tool(llm_api._build_tools(_mock_knx()), tool_name)
    converted = to_openapi(tool.parameters)["properties"][parameter]
    assert {
        key: value
        for key, value in converted.items()
        if key not in ("description", "default")
    } == expected


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


def test_serialize_result_is_json_encodable() -> None:
    """A decoded DPT 10/11/19 value must not leak non-JSON objects.

    Such a value is an xknx `KNXTime`/`KNXDate`/`KNXDateTime` holding a
    `KNXDay` enum. `asdict` leaves the enum in place, which the MCP server's
    plain `json.dumps` cannot encode.
    """
    telegram = TelegramSummary(
        timestamp="2026-08-10T12:00:00+00:00",
        source="1.1.1",
        destination="1/1/1",
        telegramtype="GroupValueWrite",
        direction="Incoming",
        dpt="10.001",
        value=DPTTime.from_knx(DPTArray((0x0C, 0x1E, 0x2D))),
        value_numeric=None,
        raw_data="0c1e2d",
        source_name="Sensor",
        destination_name="Clock",
    )
    result = llm_api._serialize(
        QueryTelegramsResult(
            telegrams=[telegram],
            total_count=1,
            offset=0,
            next_offset=None,
            limit_reached=False,
        )
    )

    assert result["telegrams"][0]["value"] == {
        "hour": 12,
        "minutes": 30,
        "seconds": 45,
        "day": 0,
    }
    json.dumps(result)  # must not raise


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (datetime(2026, 8, 10, 12, 0, tzinfo=UTC), "2026-08-10T12:00:00+00:00"),
        (date(2026, 8, 10), "2026-08-10"),
        (time(12, 30), "12:30:00"),
        ({1, 2}, [1, 2]),
        ((1, 2), [1, 2]),
    ],
)
def test_serialize_normalizes_nested_containers(
    value: object, expected: object
) -> None:
    """Nested dates, times and non-list sequences become JSON primitives."""
    result = llm_api._serialize({"v": value})
    assert result["v"] == expected
    json.dumps(result)  # must not raise


@pytest.mark.parametrize(
    ("tool_name", "args"),
    [
        pytest.param("list_dpts", {"limit": -1}, id="negative_limit"),
        pytest.param("list_dpts", {"limit": 0}, id="zero_limit"),
        pytest.param("list_dpts", {"limit": 1001}, id="limit_above_maximum"),
        pytest.param("list_dpts", {"offset": -1}, id="negative_offset"),
        pytest.param(
            "query_telegrams", {"delta_before_ms": -1}, id="negative_delta_before"
        ),
        pytest.param(
            "query_telegrams", {"delta_after_ms": -1}, id="negative_delta_after"
        ),
    ],
)
def test_pagination_bounds_are_enforced(tool_name: str, args: dict[str, Any]) -> None:
    """A negative limit disables pagination in the libraries - reject it here."""
    tool = _tool(llm_api._build_tools(_mock_knx()), tool_name)
    with pytest.raises(probatio.Invalid):
        tool.parameters(args)


def test_pagination_bounds_are_advertised_to_the_llm() -> None:
    """The model needs to see the bounds, not just be rejected by them."""
    tool = _tool(llm_api._build_tools(_mock_knx()), "list_dpts")
    properties = to_openapi(tool.parameters)["properties"]
    assert properties["limit"]["minimum"] == 1
    assert properties["limit"]["maximum"] == 1000
    assert properties["offset"]["minimum"] == 0


def test_schema_required_field_is_enforced() -> None:
    """A field without a default (ad-hoc arg) is required."""
    tool = _tool(llm_api._build_tools(_mock_knx()), "describe_dpt")
    with pytest.raises(probatio.Invalid):
        tool.parameters({})


async def test_describe_dpt_tool_call(hass: HomeAssistant) -> None:
    """A DPT tool needs no KNX runtime state and returns a serialized result."""
    tool = _tool(llm_api._build_tools(_mock_knx()), "describe_dpt")
    result = (
        await tool.async_call(
            hass,
            llm.ToolInput(tool_name="describe_dpt", tool_args={"dpt": "9.001"}),
            _llm_context(),
        )
    ).data
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
        tool = _tool(llm_api._build_tools(knx), "query_telegrams")
        result = (
            await tool.async_call(
                hass,
                llm.ToolInput(tool_name="query_telegrams", tool_args={"limit": 5}),
                _llm_context(),
            )
        ).data

    assert query.await_args.args[0] is store
    # The schema constructs the library input, so the tool never builds one.
    assert isinstance(query.await_args.args[1], QueryTelegramsInput)
    assert query.await_args.args[1].limit == 5
    assert result["total_count"] == 0


async def test_store_tool_without_store_raises(hass: HomeAssistant) -> None:
    """A store tool errors clearly when the telegram store is unavailable."""
    tool = _tool(
        llm_api._build_tools(_mock_knx(store=None)),
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
        llm_api._build_tools(_mock_knx(project=None)),
        "get_project_info",
    )
    with pytest.raises(HomeAssistantError, match="llm_no_project_loaded") as err:
        await tool.async_call(
            hass,
            llm.ToolInput(tool_name="get_project_info", tool_args={}),
            _llm_context(),
        )
    assert err.value.translation_key == "llm_no_project_loaded"


async def test_bus_write_tool_call_reaches_the_bus(
    hass: HomeAssistant, knx: KNXTestKit, hass_admin_user: MockUser
) -> None:
    """A bus tool called through the registered API sends a telegram."""
    await knx.setup_integration()
    instance = await llm.async_get_api(
        hass, llm_api.LLM_API_ID, _llm_context(hass_admin_user.id)
    )

    result = await instance.async_call_tool(
        llm.ToolInput(
            tool_name="send_group_value_write",
            tool_args={
                "group_address": "1/2/3",
                "value": 21.5,
                "value_type": "temperature",
            },
        )
    )

    await knx.assert_write("1/2/3", (0x0C, 0x33))
    # APIInstance.async_call_tool wraps a tool's return value in a ToolResult.
    assert result.data["group_address"] == "1/2/3"
    assert result.data["queued"] is True


@pytest.mark.parametrize(
    ("tool_name", "tool_args"),
    [
        pytest.param(
            "encode_value",
            {"value": 1, "value_type": "not_a_dpt"},
            id="unknown_value_type",
        ),
        pytest.param(
            "encode_value",
            {"value": "abc", "value_type": "temperature"},
            id="unencodable_value",
        ),
    ],
)
async def test_library_errors_become_translated_tool_errors(
    hass: HomeAssistant, tool_name: str, tool_args: dict[str, Any]
) -> None:
    """A library exception is reported to the model as a KNX tool failure."""
    tool = _tool(llm_api._build_tools(_mock_knx()), tool_name)

    with pytest.raises(HomeAssistantError) as err:
        await tool.async_call(
            hass,
            llm.ToolInput(tool_name=tool_name, tool_args=tool_args),
            _llm_context(),
        )
    assert err.value.translation_key == "llm_tool_failed"


@pytest.mark.parametrize(
    ("tool_args", "expected_count", "expected_next_offset"),
    [
        pytest.param({}, 100, 100, id="first_page"),
        pytest.param({"limit": 50, "offset": 2480}, 20, None, id="last_page"),
    ],
)
async def test_get_last_values_is_paginated(
    hass: HomeAssistant,
    tool_args: dict[str, Any],
    expected_count: int,
    expected_next_offset: int | None,
) -> None:
    """The library returns one entry per group address without a limit."""
    telegrams = [_telegram_summary(f"1/1/{index}") for index in range(2500)]
    knx = _mock_knx(store=Mock())

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            llm_api.kts_mcp, "get_last_values", AsyncMock(return_value=telegrams)
        )
        tool = _tool(llm_api._build_tools(knx), "get_last_values")
        result = (
            await tool.async_call(
                hass,
                llm.ToolInput(tool_name="get_last_values", tool_args=tool_args),
                _llm_context(),
            )
        ).data

    assert len(result["telegrams"]) == expected_count
    assert result["total_count"] == 2500
    assert result["next_offset"] == expected_next_offset


async def test_get_last_values_is_ordered(hass: HomeAssistant) -> None:
    """The backend query has no ORDER BY, so paging needs a stable sort."""
    telegrams = [_telegram_summary(f"1/1/{index}") for index in (3, 1, 2)]
    knx = _mock_knx(store=Mock())

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            llm_api.kts_mcp, "get_last_values", AsyncMock(return_value=telegrams)
        )
        tool = _tool(llm_api._build_tools(knx), "get_last_values")
        result = (
            await tool.async_call(
                hass,
                llm.ToolInput(tool_name="get_last_values", tool_args={}),
                _llm_context(),
            )
        ).data

    assert [telegram["destination"] for telegram in result["telegrams"]] == [
        "1/1/1",
        "1/1/2",
        "1/1/3",
    ]


async def test_get_topology_is_paginated_by_line(hass: HomeAssistant) -> None:
    """Xknxproject returns the whole topology at once, which a large bus makes huge.

    Paging on areas cannot bound it: KNX allows at most 16 of them, so any
    sensible page size covers them all and each one still carries every line
    and device address it holds. Lines are the unit that actually splits.
    """
    project = {
        "topology": {
            str(area): {
                "name": f"Area {area}",
                "description": "",
                "lines": {
                    str(line): {
                        "name": f"Line {area}.{line}",
                        "medium_type": "TP",
                        "description": "",
                        "devices": {},
                    }
                    for line in range(4)
                },
            }
            for area in range(3)
        }
    }
    tool = _tool(llm_api._build_tools(_mock_knx(project=project)), "get_topology")

    result = (
        await tool.async_call(
            hass,
            llm.ToolInput(tool_name="get_topology", tool_args={"limit": 5}),
            _llm_context(),
        )
    ).data

    # Three areas, twelve lines: a limit of 5 has to bite on the lines.
    assert len(result["lines"]) == 5
    assert result["total_count"] == 12
    assert result["next_offset"] == 5
    assert result["limit_reached"] is True
    # The area grouping survives the flattening.
    assert result["lines"][0]["area"] == "Area 0"
