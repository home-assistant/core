"""Tests for the blueprint LLM tools."""

import probatio
import pytest
from pytest_homeassistant.common import MockUser

from homeassistant.components.blueprint import DOMAIN
from homeassistant.components.blueprint.llm import (
    GetBlueprintTool,
    ListBlueprintsTool,
    async_get_tools,
)
from homeassistant.core import Context, HomeAssistant
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
async def setup_blueprints(hass: HomeAssistant) -> None:
    """Set up the automation and script blueprints of the test configuration."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, "automation", {})
    assert await async_setup_component(hass, "script", {})


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
        "blueprint__list_blueprints",
        "blueprint__get_blueprint",
    ]


@pytest.mark.usefixtures("setup_blueprints")
async def test_list_blueprints(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test listing the blueprints sorted by domain and name."""
    assert await _call(hass, llm_context, ListBlueprintsTool(), {}) == {
        "blueprints": [
            {
                "domain": "automation",
                "path": "test_event_service.yaml",
                "name": "Call service based on event",
            },
            {
                "domain": "automation",
                "path": "test_event_service_legacy_schema.yaml",
                "name": "Call service based on event",
            },
            {
                "domain": "automation",
                "path": "in_folder/in_folder_blueprint.yaml",
                "name": "In Folder Blueprint",
            },
            {
                "domain": "script",
                "path": "test_service.yaml",
                "name": "Call service",
            },
        ]
    }


@pytest.mark.usefixtures("setup_blueprints")
async def test_list_blueprints_of_domain(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test listing the blueprints of one domain."""
    result = await _call(hass, llm_context, ListBlueprintsTool(), {"domain": "script"})

    assert [item["path"] for item in result["blueprints"]] == ["test_service.yaml"]


async def test_list_without_blueprints(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test the list is empty when no domain uses blueprints."""
    assert await _call(hass, llm_context, ListBlueprintsTool(), {}) == {
        "blueprints": []
    }


@pytest.mark.usefixtures("setup_blueprints")
async def test_get_blueprint(hass: HomeAssistant, llm_context: llm.LLMContext) -> None:
    """Test getting a blueprint as YAML with its inputs."""
    result = await _call(
        hass,
        llm_context,
        GetBlueprintTool(),
        {"domain": "script", "path": "test_service.yaml"},
    )

    assert result == {
        "domain": "script",
        "path": "test_service.yaml",
        "yaml": result["yaml"],
    }
    assert "service_to_call:" in result["yaml"]
    assert "!input service_to_call" in result["yaml"]


@pytest.mark.usefixtures("setup_blueprints")
@pytest.mark.parametrize(
    ("domain", "path"),
    [
        ("script", "unknown.yaml"),
        ("light", "test_service.yaml"),
        # Only paths in the blueprint folder of the domain are read
        ("script", "../automation/test_event_service.yaml"),
    ],
)
async def test_get_blueprint_not_found(
    hass: HomeAssistant, llm_context: llm.LLMContext, domain: str, path: str
) -> None:
    """Test an unknown blueprint is not found."""
    tool = GetBlueprintTool()
    with pytest.raises(HomeAssistantError, match="not found"):
        await tool.async_call(
            hass,
            llm.ToolInput(tool.name, {"domain": domain, "path": path}),
            llm_context,
        )


async def test_get_blueprint_invalid_parameters(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test the domain and path are required."""
    tool = GetBlueprintTool()
    with pytest.raises(probatio.Invalid):
        await tool.async_call(
            hass, llm.ToolInput(tool.name, {"domain": "script"}), llm_context
        )


async def test_call_through_api(
    hass: HomeAssistant, hass_admin_user: MockUser, llm_context: llm.LLMContext
) -> None:
    """Test the tools are available through the Home Assistant API."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, "llm", {})
    llm_context.context = Context(user_id=hass_admin_user.id)

    api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)
    tool = next(tool for tool in api.tools if tool.name == "blueprint__get_blueprint")
    assert tool.integration == DOMAIN
    assert tool.annotations == llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
