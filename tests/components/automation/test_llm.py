"""Tests for the automation LLM tools."""

from unittest.mock import patch

import probatio
import pytest
from pytest_homeassistant.common import MockUser

from homeassistant.components.automation import DOMAIN
from homeassistant.components.automation.llm import (
    GetConfigTool,
    ListAutomationsTool,
    async_get_tools,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    category_registry as cr,
    entity_registry as er,
    label_registry as lr,
    llm,
)
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
async def setup_automations(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    category_registry: cr.CategoryRegistry,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Set up an automation that ran, one that is off and one with an error."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {
                    "id": "kitchen",
                    "alias": "Kitchen lights",
                    "description": "Turn on the kitchen lights in the evening",
                    "triggers": {"trigger": "event", "event_type": "test_event"},
                    "actions": [],
                },
                {
                    "id": "bedroom",
                    "alias": "Bedroom",
                    "description": 0,
                    "initial_state": False,
                    "triggers": {"trigger": "event", "event_type": "test_event"},
                    "actions": [],
                },
                {
                    "id": "broken",
                    "alias": "Broken",
                    "triggers": {"trigger": "unknown_platform"},
                    "actions": [],
                },
            ]
        },
    )
    category = category_registry.async_create(scope=DOMAIN, name="Lighting")
    labels = {
        label_registry.async_create(name).label_id for name in ("Kitchen", "Evening")
    }
    entity_registry.async_update_entity(
        "automation.kitchen_lights",
        area_id=area_registry.async_create("Kitchen").id,
        categories={DOMAIN: category.category_id},
        labels=labels,
    )
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()


async def _call(
    hass: HomeAssistant, llm_context: llm.LLMContext, tool_args: JsonObjectType
) -> JsonObjectType:
    """Call the tool and return its result."""
    tool = ListAutomationsTool()
    result = await tool.async_call(
        hass, llm.ToolInput(tool.name, tool_args), llm_context
    )
    assert result.error is False
    return result.data


async def test_async_get_tools(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test the tool is only provided for the Home Assistant API."""
    assert async_get_tools(hass, llm_context, llm.LLM_API_ASSIST) is None

    tools = async_get_tools(hass, llm_context, llm.LLM_API_HOME_ASSISTANT)
    assert tools is not None
    assert [tool.name for tool in tools.tools] == [
        "automation__list_automations",
        "automation__get_config",
    ]


@pytest.mark.freeze_time("2026-11-24 12:00:00+00:00")
@pytest.mark.usefixtures("setup_automations")
async def test_list_automations(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test listing the automations sorted by name."""
    assert await _call(hass, llm_context, {}) == {
        "automations": [
            {
                "entity_id": "automation.bedroom",
                "name": "Bedroom",
                "state": "off",
                "last_triggered": None,
                "description": "0",
            },
            {
                "entity_id": "automation.broken",
                "name": "Broken",
                "state": "unavailable",
                "last_triggered": None,
            },
            {
                "entity_id": "automation.kitchen_lights",
                "name": "Kitchen lights",
                "state": "on",
                "last_triggered": "2026-11-24T12:00:00+00:00",
                "description": "Turn on the kitchen lights in the evening",
                "area": "Kitchen",
                "category": "Lighting",
                "labels": ["Evening", "Kitchen"],
            },
        ],
        "total": 3,
    }


@pytest.mark.usefixtures("setup_automations")
async def test_list_automations_pages(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test the next_offset points to the next page."""
    with patch("homeassistant.components.automation.llm._LIMIT", 2):
        first = await _call(hass, llm_context, {})
        second = await _call(hass, llm_context, {"offset": first["next_offset"]})

    assert [item["name"] for item in first["automations"]] == ["Bedroom", "Broken"]
    assert first["next_offset"] == 2
    assert [item["name"] for item in second["automations"]] == ["Kitchen lights"]
    assert "next_offset" not in second


async def test_list_without_automations(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test the list is empty when the automation integration is not set up."""
    assert await _call(hass, llm_context, {}) == {"automations": [], "total": 0}


@pytest.mark.parametrize("offset", [-1, "first"])
async def test_invalid_offset(
    hass: HomeAssistant, llm_context: llm.LLMContext, offset: object
) -> None:
    """Test an invalid offset is rejected by the schema."""
    tool = ListAutomationsTool()
    with pytest.raises(probatio.Invalid):
        await tool.async_call(
            hass, llm.ToolInput(tool.name, {"offset": offset}), llm_context
        )


async def test_call_through_api(
    hass: HomeAssistant, hass_admin_user: MockUser, llm_context: llm.LLMContext
) -> None:
    """Test the tool is available through the Home Assistant API."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, "llm", {})
    llm_context.context = Context(user_id=hass_admin_user.id)

    api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)
    tool = next(
        tool for tool in api.tools if tool.name == "automation__list_automations"
    )
    assert tool.integration == DOMAIN
    assert await api.async_call_tool(llm.ToolInput(tool.name, {})) == llm.ToolResult(
        data={"automations": [], "total": 0}
    )


@pytest.mark.usefixtures("setup_automations")
async def test_get_config(hass: HomeAssistant, llm_context: llm.LLMContext) -> None:
    """Test getting the configuration of an automation."""
    tool = GetConfigTool()
    result = await tool.async_call(
        hass,
        llm.ToolInput(tool.name, {"entity_id": "automation.kitchen_lights"}),
        llm_context,
    )

    assert result == llm.ToolResult(
        data={
            "entity_id": "automation.kitchen_lights",
            "config": {
                "id": "kitchen",
                "alias": "Kitchen lights",
                "description": "Turn on the kitchen lights in the evening",
                "triggers": {"trigger": "event", "event_type": "test_event"},
                "actions": [],
            },
        }
    )


@pytest.mark.usefixtures("setup_automations")
async def test_get_config_of_broken_automation(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test the configuration of an automation with an error is returned."""
    tool = GetConfigTool()
    result = await tool.async_call(
        hass, llm.ToolInput(tool.name, {"entity_id": "automation.broken"}), llm_context
    )

    assert result.data["config"]["triggers"] == {"trigger": "unknown_platform"}


@pytest.mark.usefixtures("setup_automations")
async def test_get_config_not_found(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test an unknown automation is not found."""
    tool = GetConfigTool()
    with pytest.raises(HomeAssistantError, match="not found"):
        await tool.async_call(
            hass,
            llm.ToolInput(tool.name, {"entity_id": "automation.unknown"}),
            llm_context,
        )


async def test_get_config_without_automations(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test no automation is found when the integration is not set up."""
    tool = GetConfigTool()
    with pytest.raises(HomeAssistantError, match="not found"):
        await tool.async_call(
            hass,
            llm.ToolInput(tool.name, {"entity_id": "automation.kitchen_lights"}),
            llm_context,
        )


async def test_get_config_only_automations(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test only automation entity IDs are accepted."""
    tool = GetConfigTool()
    with pytest.raises(probatio.Invalid):
        await tool.async_call(
            hass, llm.ToolInput(tool.name, {"entity_id": "script.test"}), llm_context
        )


async def test_get_config_of_blueprint_automation(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test an automation made from a blueprint returns the blueprint and inputs."""
    use_blueprint = {
        "path": "test_event_service.yaml",
        "input": {
            "trigger_event": "blueprint_event",
            "service_to_call": "test.automation",
            "a_number": 5,
        },
    }
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "id": "from_blueprint",
                "alias": "From blueprint",
                "use_blueprint": use_blueprint,
            }
        },
    )

    tool = GetConfigTool()
    result = await tool.async_call(
        hass,
        llm.ToolInput(tool.name, {"entity_id": "automation.from_blueprint"}),
        llm_context,
    )

    assert hass.states.get("automation.from_blueprint").state == "on"
    assert result.data["config"] == {
        "id": "from_blueprint",
        "alias": "From blueprint",
        "use_blueprint": use_blueprint,
    }
