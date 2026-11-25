"""Tests for the trace LLM tools."""

from typing import Any

import probatio
import pytest
from pytest_homeassistant.common import MockUser, async_load_json_object_fixture

from homeassistant.components.trace import DOMAIN
from homeassistant.components.trace.llm import (
    GetTraceTool,
    ListTracesTool,
    async_get_tools,
)
from homeassistant.core import Context, CoreState, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonObjectType


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
async def run_automation(hass: HomeAssistant) -> None:
    """Run an automation that calls a script twice."""
    assert await async_setup_component(
        hass,
        "script",
        {"script": {"cleanup": {"sequence": [{"event": "cleanup_done"}]}}},
    )
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "kitchen",
                    "alias": "Kitchen",
                    "triggers": {"trigger": "event", "event_type": "test_event"},
                    "actions": [
                        {"event": "kitchen_done"},
                        {"action": "script.cleanup"},
                    ],
                },
                {
                    "alias": "Without id",
                    "triggers": {"trigger": "event", "event_type": "test_event"},
                    "actions": [],
                },
            ]
        },
    )
    for _ in range(2):
        hass.bus.async_fire("test_event")
        await hass.async_block_till_done()


async def _call(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    tool: llm.Tool,
    tool_args: JsonObjectType,
) -> JsonObjectType:
    """Call a tool and return its result."""
    result = await tool.async_call(
        hass, llm.ToolInput(tool.name, tool_args), llm_context
    )
    assert result.error is False
    return result.data


async def test_async_get_tools(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test the tools are only provided for the Home Assistant API."""
    assert async_get_tools(hass, llm_context, llm.LLM_API_ASSIST) is None

    tools = async_get_tools(hass, llm_context, llm.LLM_API_HOME_ASSISTANT)
    assert tools is not None
    assert [tool.name for tool in tools.tools] == [
        "trace__list_traces",
        "trace__get_trace",
    ]


@pytest.mark.usefixtures("run_automation")
async def test_list_traces(hass: HomeAssistant, llm_context: llm.LLMContext) -> None:
    """Test listing the runs of an automation, newest first."""
    result = await _call(
        hass, llm_context, ListTracesTool(), {"entity_id": "automation.kitchen"}
    )

    traces = result["traces"]
    assert len(traces) == 2
    assert traces[0]["start"] > traces[1]["start"]
    assert len({trace["trace_id"] for trace in traces}) == 2
    for trace in traces:
        assert trace["trace_id"].startswith("automation:")
        assert {key: value for key, value in trace.items() if key != "trace_id"} == {
            "start": trace["start"],
            "finish": trace["finish"],
            "state": "stopped",
            "script_execution": "finished",
            "last_step": "action/1",
            "trigger": "event 'test_event'",
        }


@pytest.mark.usefixtures("run_automation")
async def test_get_trace(hass: HomeAssistant, llm_context: llm.LLMContext) -> None:
    """Test getting the steps of a run, with the run of the script it called."""
    listed = await _call(
        hass, llm_context, ListTracesTool(), {"entity_id": "automation.kitchen"}
    )
    trace_id = listed["traces"][0]["trace_id"]

    result = await _call(hass, llm_context, GetTraceTool(), {"trace_id": trace_id})

    assert {key: result[key] for key in listed["traces"][0]} == listed["traces"][0]
    assert result["entity_id"] == "automation.kitchen"
    assert result["config"]["id"] == "kitchen"
    assert [step["path"] for step in result["steps"]] == [
        "trigger/0",
        "action/0",
        "action/1",
    ]
    child_trace_id = result["steps"][2]["child_trace_id"]
    assert child_trace_id.startswith("script:")

    script_result = await _call(
        hass, llm_context, GetTraceTool(), {"trace_id": child_trace_id}
    )
    assert script_result["entity_id"] == "script.cleanup"
    assert [step["path"] for step in script_result["steps"]] == ["sequence/0"]


@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_restored_traces(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    llm_context: llm.LLMContext,
    domain: str,
) -> None:
    """Test listing and getting runs restored from storage."""
    hass.set_state(CoreState.not_running)
    hass_storage["trace.saved_traces"] = await async_load_json_object_fixture(
        hass, f"{domain}_saved_traces.json", "trace"
    )
    if domain == "automation":
        config = {
            "automation": [{"id": "sun", "alias": "Sun", "triggers": [], "actions": []}]
        }
    else:
        config = {"script": {"sun": {"sequence": []}}}
    assert await async_setup_component(hass, domain, config)
    await hass.async_start()
    await hass.async_block_till_done()

    listed = await _call(
        hass, llm_context, ListTracesTool(), {"entity_id": f"{domain}.sun"}
    )
    assert len(listed["traces"]) == 1
    restored = listed["traces"][0]
    assert restored["trace_id"].startswith(f"{domain}:")
    assert (
        restored["start"]
        == hass_storage["trace.saved_traces"]["data"][f"{domain}.sun"][0]["short_dict"][
            "timestamp"
        ]["start"]
    )

    result = await _call(
        hass, llm_context, GetTraceTool(), {"trace_id": restored["trace_id"]}
    )
    assert result["entity_id"] == f"{domain}.sun"
    assert result["steps"]


@pytest.mark.usefixtures("run_automation")
@pytest.mark.parametrize(
    "entity_id", ["automation.without_id", "automation.unknown", "script.unknown"]
)
async def test_list_traces_not_found(
    hass: HomeAssistant, llm_context: llm.LLMContext, entity_id: str
) -> None:
    """Test an automation without id or an unknown entity has no traces."""
    tool = ListTracesTool()
    with pytest.raises(HomeAssistantError, match="not found"):
        await tool.async_call(
            hass, llm.ToolInput(tool.name, {"entity_id": entity_id}), llm_context
        )


@pytest.mark.usefixtures("run_automation")
@pytest.mark.parametrize(
    "trace_id", ["automation", "automation:abc", "light:abcd", "automation:zzzz"]
)
async def test_get_trace_not_found(
    hass: HomeAssistant, llm_context: llm.LLMContext, trace_id: str
) -> None:
    """Test an unknown or malformed trace_id is not found."""
    tool = GetTraceTool()
    with pytest.raises(HomeAssistantError, match="not found"):
        await tool.async_call(
            hass, llm.ToolInput(tool.name, {"trace_id": trace_id}), llm_context
        )


@pytest.mark.parametrize("entity_id", ["light.kitchen", "not an entity id"])
async def test_list_traces_invalid_entity_id(
    hass: HomeAssistant, llm_context: llm.LLMContext, entity_id: str
) -> None:
    """Test only automations and scripts are accepted."""
    tool = ListTracesTool()
    with pytest.raises(probatio.Invalid):
        await tool.async_call(
            hass, llm.ToolInput(tool.name, {"entity_id": entity_id}), llm_context
        )


async def test_call_through_api(
    hass: HomeAssistant, hass_admin_user: MockUser, llm_context: llm.LLMContext
) -> None:
    """Test the tools are available through the Home Assistant API."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, "llm", {})
    llm_context.context = Context(user_id=hass_admin_user.id)

    api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)
    tool = next(tool for tool in api.tools if tool.name == "trace__get_trace")
    assert tool.integration == DOMAIN
    assert tool.annotations == llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
