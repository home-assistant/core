"""Tests for the calendar LLM tools platform."""

from datetime import timedelta

from freezegun import freeze_time
import pytest

from homeassistant.components import calendar, llm as llm_component
from homeassistant.components.calendar import llm as calendar_llm
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.core import Context, HomeAssistant, SupportsResponse
from homeassistant.helpers import entity_registry as er, llm
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_mock_service

ENTITY_ID = "calendar.test_calendar"


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations and expose a calendar."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "calendar", {})
    assert await async_setup_component(hass, "llm", {})
    hass.states.async_set(ENTITY_ID, "on", {"friendly_name": "Mock Calendar Name"})
    async_expose_entity(hass, "conversation", ENTITY_ID, True)
    await hass.async_block_till_done()


def _llm_context() -> llm.LLMContext:
    """Return an LLM context for the conversation assistant."""
    return llm.LLMContext(
        platform="test_platform",
        context=Context(),
        language="*",
        assistant="conversation",
        device_id=None,
    )


async def test_get_tools_no_exposed_calendar(hass: HomeAssistant) -> None:
    """Test no calendar tool is offered when no calendar is exposed."""
    async_expose_entity(hass, "conversation", ENTITY_ID, False)
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    assert "calendar_get_events" not in [tool.name for tool in result.tools]
    assert calendar_llm.async_get_tools(hass, _llm_context(), "assist") is None


async def test_no_tools_for_other_api(hass: HomeAssistant) -> None:
    """Test the platform returns None for an unsupported API."""
    assert calendar_llm.async_get_tools(hass, _llm_context(), "other") is None


async def test_calendar_get_events_tool(hass: HomeAssistant) -> None:
    """Test the calendar get events tool is exposed and works via the platform."""
    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context, "assist")
    tool = next(
        (tool for tool in result.tools if tool.name == "calendar_get_events"), None
    )
    assert tool is not None
    assert tool.parameters.schema["calendar"].container == ["Mock Calendar Name"]

    calls = async_mock_service(
        hass,
        domain=calendar.DOMAIN,
        service=calendar.SERVICE_GET_EVENTS,
        schema=calendar.SERVICE_GET_EVENTS_SCHEMA,
        response={
            ENTITY_ID: {
                "events": [
                    {
                        "start": "2025-09-17",
                        "end": "2025-09-18",
                        "summary": "Home Assistant 12th birthday",
                        "description": "",
                    },
                    {
                        "start": "2025-09-17T14:00:00-05:00",
                        "end": "2025-09-18T15:00:00-05:00",
                        "summary": "Champagne",
                        "description": "",
                    },
                ]
            }
        },
        supports_response=SupportsResponse.ONLY,
    )

    tool_input = llm.ToolInput(
        tool_name="calendar_get_events",
        tool_args={"calendar": "Mock Calendar Name", "range": "today"},
    )
    now = dt_util.now()
    with freeze_time(now):
        response = await tool.async_call(hass, tool_input, llm_context)

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == calendar.DOMAIN
    assert call.service == calendar.SERVICE_GET_EVENTS
    assert call.data == {
        "entity_id": [ENTITY_ID],
        "start_date_time": now,
        "end_date_time": dt_util.start_of_local_day(now) + timedelta(days=1),
    }

    assert response == {
        "success": True,
        "result": [
            {
                "start": "2025-09-17",
                "end": "2025-09-18",
                "summary": "Home Assistant 12th birthday",
                "description": "",
                "all_day": True,
            },
            {
                "start": "2025-09-17T14:00:00-05:00",
                "end": "2025-09-18T15:00:00-05:00",
                "summary": "Champagne",
                "description": "",
            },
        ],
    }

    # The "week" range searches seven days out.
    calls.clear()
    tool_input.tool_args["range"] = "week"
    with freeze_time(now):
        await tool.async_call(hass, tool_input, llm_context)
    assert call.domain == calendar.DOMAIN
    assert calls[0].data["end_date_time"] == (
        dt_util.start_of_local_day(now) + timedelta(days=7)
    )


async def test_calendar_get_events_tool_not_found(hass: HomeAssistant) -> None:
    """Test the tool reports when the requested calendar no longer matches."""
    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context, "assist")
    tool = next(tool for tool in result.tools if tool.name == "calendar_get_events")

    # Unexpose after the tool (and its calendar enum) was built, so the call-time
    # match no longer finds the calendar.
    async_expose_entity(hass, "conversation", ENTITY_ID, False)
    response = await tool.async_call(
        hass,
        llm.ToolInput(
            "calendar_get_events", {"calendar": "Mock Calendar Name", "range": "today"}
        ),
        llm_context,
    )
    assert response == {"success": False, "error": "Calendar not found"}


async def test_calendar_get_events_tool_uses_aliases(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test exposed calendar aliases are offered as valid tool values."""
    entry = entity_registry.async_get_or_create(
        "calendar", "test", "aliased", suggested_object_id="aliased"
    )
    entity_registry.async_update_entity(entry.entity_id, aliases={"Family Calendar"})
    hass.states.async_set(entry.entity_id, "on")
    async_expose_entity(hass, "conversation", entry.entity_id, True)

    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    tool = next(tool for tool in result.tools if tool.name == "calendar_get_events")
    assert "Family Calendar" in tool.parameters.schema["calendar"].container
