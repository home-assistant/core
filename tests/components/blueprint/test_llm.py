"""Tests for the blueprint LLM tools."""

from collections.abc import Generator
from unittest.mock import patch

import probatio
import pytest
from pytest_homeassistant.common import MockUser

from homeassistant.components.blueprint import BLUEPRINT_SCHEMA, DOMAIN, errors, models
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


@pytest.fixture
def other_blueprints(hass: HomeAssistant) -> Generator[None]:
    """Replace the automation blueprints with one with metadata and a broken one."""
    blueprints = {
        "with_metadata.yaml": models.Blueprint(
            {
                "blueprint": {
                    "name": "With metadata",
                    "domain": "automation",
                    "description": "Turns on a light when motion is seen.",
                    "author": "Jane",
                    "source_url": "https://example.com/with_metadata.yaml",
                    "input": {},
                }
            },
            schema=BLUEPRINT_SCHEMA,
        ),
        "broken.yaml": errors.FailedToLoad(
            "automation", "broken.yaml", FileNotFoundError("Missing file")
        ),
    }
    with patch.object(
        hass.data[DOMAIN]["automation"],
        "async_get_blueprints",
        return_value=blueprints,
    ):
        yield


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


@pytest.mark.usefixtures("setup_blueprints", "other_blueprints")
async def test_list_blueprints_with_metadata_and_error(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test the metadata of a blueprint, and the error of a broken one."""
    result = await _call(
        hass, llm_context, ListBlueprintsTool(), {"domain": "automation"}
    )

    assert result == {
        "blueprints": [
            {
                "domain": "automation",
                "path": "broken.yaml",
                "error": "Failed to load blueprint: Missing file",
            },
            {
                "domain": "automation",
                "path": "with_metadata.yaml",
                "name": "With metadata",
                "description": "Turns on a light when motion is seen.",
                "author": "Jane",
                "source_url": "https://example.com/with_metadata.yaml",
            },
        ]
    }


@pytest.mark.usefixtures("setup_blueprints")
async def test_domain_ignores_case(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test the domain matches in any case."""
    listed = await _call(
        hass, llm_context, ListBlueprintsTool(), {"domain": " Script "}
    )
    assert [item["path"] for item in listed["blueprints"]] == ["test_service.yaml"]

    result = await _call(
        hass,
        llm_context,
        GetBlueprintTool(),
        {"domain": "Script", "path": "test_service.yaml"},
    )
    assert result["domain"] == "script"


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


@pytest.mark.usefixtures("setup_blueprints", "other_blueprints")
async def test_get_blueprint_with_metadata(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test the YAML of a blueprint holds its metadata."""
    result = await _call(
        hass,
        llm_context,
        GetBlueprintTool(),
        {"domain": "automation", "path": "with_metadata.yaml"},
    )

    assert "description: Turns on a light when motion is seen." in result["yaml"]
    assert "author: Jane" in result["yaml"]
    assert "source_url: https://example.com/with_metadata.yaml" in result["yaml"]


@pytest.mark.usefixtures("setup_blueprints", "other_blueprints")
async def test_get_blueprint_failed_to_load(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test a blueprint that failed to load returns its error."""
    tool = GetBlueprintTool()
    with pytest.raises(
        HomeAssistantError,
        match="Blueprint 'automation/broken.yaml' failed to load: Failed to load "
        "blueprint: Missing file",
    ):
        await tool.async_call(
            hass,
            llm.ToolInput(tool.name, {"domain": "automation", "path": "broken.yaml"}),
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
