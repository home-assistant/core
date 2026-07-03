"""Tests for the calendar LLM tools platform."""

from datetime import timedelta

from freezegun import freeze_time
import pytest

from homeassistant.components import calendar, llm as llm_component
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.core import Context, HomeAssistant, SupportsResponse
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_mock_service


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations for the calendar LLM tools platform."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "calendar", {})
    assert await async_setup_component(hass, "llm", {})
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
    result = await llm_component.async_get_tools(hass, _llm_context())
    assert [tool.name for tool in result.tools] == []


async def test_calendar_get_events_tool(hass: HomeAssistant) -> None:
    """Test the calendar get events tool is exposed and works via the platform."""
    hass.states.async_set(
        "calendar.test_calendar", "on", {"friendly_name": "Mock Calendar Name"}
    )
    async_expose_entity(hass, "conversation", "calendar.test_calendar", True)

    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context)
    tool = next(
        (tool for tool in result.tools if tool.name == "calendar_get_events"), None
    )
    assert tool is not None

    calls = async_mock_service(
        hass,
        domain=calendar.DOMAIN,
        service=calendar.SERVICE_GET_EVENTS,
        schema=calendar.SERVICE_GET_EVENTS_SCHEMA,
        response={
            "calendar.test_calendar": {
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
        "entity_id": ["calendar.test_calendar"],
        "start_date_time": now,
        "end_date_time": dt_util.start_of_local_day() + timedelta(days=1),
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
