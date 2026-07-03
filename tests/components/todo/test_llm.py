"""Tests for the todo LLM tools platform."""

from homeassistant.components import llm as llm_component, todo
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv, llm
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


def _llm_context() -> llm.LLMContext:
    """Return an LLM context for the conversation assistant."""
    return llm.LLMContext(
        platform="test_platform",
        context=Context(),
        language="*",
        assistant="conversation",
        device_id=None,
    )


async def test_get_tools_no_exposed_todo(hass: HomeAssistant) -> None:
    """Test no todo tool is offered when no to-do list is exposed."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "todo", {})
    assert await async_setup_component(hass, "llm", {})

    result = await llm_component.async_get_tools(hass, _llm_context())
    assert [tool.name for tool in result.tools] == []


async def test_todo_get_items_tool(hass: HomeAssistant) -> None:
    """Test the todo get items tool is exposed and works via the platform."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "todo", {})
    assert await async_setup_component(hass, "llm", {})
    hass.states.async_set(
        "todo.test_list", "0", {"friendly_name": "Mock Todo List Name"}
    )
    async_expose_entity(hass, "conversation", "todo.test_list", True)

    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context)
    tool = next((tool for tool in result.tools if tool.name == "todo_get_items"), None)
    assert tool is not None
    assert tool.parameters.schema["todo_list"].container == ["Mock Todo List Name"]

    calls = async_mock_service(
        hass,
        domain=todo.DOMAIN,
        service=todo.TodoServices.GET_ITEMS,
        schema=cv.make_entity_service_schema(todo.TODO_SERVICE_GET_ITEMS_SCHEMA),
        response={
            "todo.test_list": {
                "items": [
                    {"uid": "1234", "summary": "Buy milk", "status": "needs_action"},
                ]
            }
        },
    )

    result = await tool.async_call(
        hass,
        llm.ToolInput("todo_get_items", {"todo_list": "Mock Todo List Name"}),
        llm_context,
    )

    assert len(calls) == 1
    assert calls[0].data == {
        "entity_id": ["todo.test_list"],
        "status": ["needs_action"],
    }
    assert result == {
        "success": True,
        "result": [{"uid": "1234", "status": "needs_action", "summary": "Buy milk"}],
    }
