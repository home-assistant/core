"""Tests for the scene LLM tools."""

from unittest.mock import patch

import probatio
import pytest
from pytest_homeassistant.common import MockUser

from homeassistant.components.scene import DOMAIN
from homeassistant.components.scene.llm import ListScenesTool, async_get_tools
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonObjectType

EXPECTED_SCENES = [
    {"entity_id": "scene.bedtime", "name": "Bedtime", "last_activated": None},
    {
        "entity_id": "scene.broken",
        "name": "Broken",
        "last_activated": None,
        "available": False,
    },
    {
        "entity_id": "scene.movie_night",
        "name": "Movie night",
        "last_activated": "2026-11-24T12:00:00+00:00",
    },
]


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
async def setup_scenes(hass: HomeAssistant) -> None:
    """Set up an activated scene, a scene never activated and an unavailable one."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {"name": "Movie night", "entities": {"light.tv": "on"}},
                {"name": "Bedtime", "entities": {"light.tv": "off"}},
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        DOMAIN, "turn_on", {"entity_id": "scene.movie_night"}, blocking=True
    )
    hass.states.async_set(
        "scene.broken", STATE_UNAVAILABLE, {"friendly_name": "Broken"}
    )


async def _call(
    hass: HomeAssistant, llm_context: llm.LLMContext, tool_args: JsonObjectType
) -> JsonObjectType:
    """Call the tool and return its result."""
    tool = ListScenesTool()
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
    assert [tool.name for tool in tools.tools] == ["scene__list_scenes"]


@pytest.mark.freeze_time("2026-11-24 12:00:00+00:00")
@pytest.mark.usefixtures("setup_scenes")
async def test_list_scenes(hass: HomeAssistant, llm_context: llm.LLMContext) -> None:
    """Test listing the scenes sorted by name."""
    assert await _call(hass, llm_context, {}) == {
        "scenes": EXPECTED_SCENES,
        "total": 3,
    }


@pytest.mark.freeze_time("2026-11-24 12:00:00+00:00")
@pytest.mark.usefixtures("setup_scenes")
async def test_list_scenes_pages(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test the next_offset points to the next page."""
    with patch("homeassistant.components.scene.llm._LIMIT", 2):
        first = await _call(hass, llm_context, {})
        second = await _call(hass, llm_context, {"offset": first["next_offset"]})

    assert first == {"scenes": EXPECTED_SCENES[:2], "total": 3, "next_offset": 2}
    assert second == {"scenes": EXPECTED_SCENES[2:], "total": 3}


@pytest.mark.parametrize("offset", [-1, "first"])
async def test_invalid_offset(
    hass: HomeAssistant, llm_context: llm.LLMContext, offset: object
) -> None:
    """Test an invalid offset is rejected by the schema."""
    tool = ListScenesTool()
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
    tool = next(tool for tool in api.tools if tool.name == "scene__list_scenes")
    assert tool.integration == DOMAIN
    assert await api.async_call_tool(llm.ToolInput(tool.name, {})) == llm.ToolResult(
        data={"scenes": [], "total": 0}
    )
