"""Tests for the intent_script LLM tools platform."""

import pytest

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.intent_script import llm as intent_script_llm
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

LIGHT_ENTITY_ID = "light.kitchen"


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations and configure intent scripts."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(
        hass,
        "intent_script",
        {
            "intent_script": {
                "Tell a joke": {
                    "description": "Tell a joke",
                    "speech": {"text": "Why did the chicken cross the road?"},
                },
                "LightAction": {
                    "description": "Do a light thing",
                    "platforms": ["light"],
                    "speech": {"text": "Done"},
                },
            }
        },
    )
    assert await async_setup_component(hass, "llm", {})
    hass.states.async_set(LIGHT_ENTITY_ID, "on", {"friendly_name": "Kitchen Light"})
    async_expose_entity(hass, "conversation", LIGHT_ENTITY_ID, True)
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


async def _tool_names(hass: HomeAssistant) -> set[str]:
    """Return the names of the tools offered by the intent_script platform."""
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    return {tool.name for tool in result.tools}


async def test_intent_scripts_exposed(hass: HomeAssistant) -> None:
    """Test intent scripts are exposed as LLM tools with slugified names."""
    names = await _tool_names(hass)
    # The user-provided "Tell a joke" name is slugified into a valid tool name.
    assert "Tell_a_joke" in names
    assert "LightAction" in names


async def test_intent_script_platform_filtered(hass: HomeAssistant) -> None:
    """Test a platform-restricted intent script requires an exposed entity."""
    async_expose_entity(hass, "conversation", LIGHT_ENTITY_ID, False)
    names = await _tool_names(hass)
    assert "LightAction" not in names
    # Unrestricted intent scripts stay exposed.
    assert "Tell_a_joke" in names


async def test_no_tools_for_other_api(hass: HomeAssistant) -> None:
    """Test the platform returns None for an unsupported API."""
    assert intent_script_llm.async_get_tools(hass, _llm_context(), "other") is None
