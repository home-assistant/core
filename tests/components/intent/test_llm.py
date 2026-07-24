"""Tests for the intent LLM tools platform (generic intents)."""

import pytest

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.intent import llm as intent_llm
from homeassistant.components.local_timer_list import LocalTimerListEntity
from homeassistant.components.timer_list import (
    DATA_COMPONENT as TIMER_LIST_DATA_COMPONENT,
    DOMAIN as TIMER_LIST_DOMAIN,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, llm
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

COVER_ENTITY_ID = "cover.test"


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations and expose a cover."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "llm", {})
    hass.states.async_set(COVER_ENTITY_ID, "open", {"friendly_name": "Test Cover"})
    async_expose_entity(hass, "conversation", COVER_ENTITY_ID, True)
    await hass.async_block_till_done()


def _llm_context(device_id: str | None = None) -> llm.LLMContext:
    """Return an LLM context for the conversation assistant."""
    return llm.LLMContext(
        platform="test_platform",
        context=Context(),
        language="*",
        assistant="conversation",
        device_id=device_id,
    )


async def _tool_names(hass: HomeAssistant) -> set[str]:
    """Return the names of the tools offered by the intent platform."""
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    return {tool.name for tool in result.tools}


async def test_generic_intents_exposed(hass: HomeAssistant) -> None:
    """Test the always-on generic intents are exposed."""
    names = await _tool_names(hass)
    assert "HassTurnOn" in names
    assert "HassTurnOff" in names


async def test_timer_intents_require_timer_device(hass: HomeAssistant) -> None:
    """Test timer intents are not exposed without a timer-capable device."""
    assert "HassStartTimer" not in await _tool_names(hass)


async def _add_timer_device(hass: HomeAssistant) -> str:
    """Create a device with a timer_list entity and return its device id."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("test", entry.entry_id)},
    )
    component = hass.data[TIMER_LIST_DATA_COMPONENT]
    await component.async_add_entities(
        [LocalTimerListEntity(name="Timers", unique_id=device.id)]
    )
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        TIMER_LIST_DOMAIN, TIMER_LIST_DOMAIN, device.id
    )
    assert entity_id is not None
    entity_registry.async_update_entity(entity_id, device_id=device.id)
    return device.id


async def test_timer_intents_offered_for_timer_device(hass: HomeAssistant) -> None:
    """Test timer intents are exposed for a device with a timer_list entity."""
    device_id = await _add_timer_device(hass)

    result = await llm_component.async_get_tools(
        hass, _llm_context(device_id=device_id), "assist"
    )
    names = {tool.name for tool in result.tools}
    assert "HassStartTimer" in names
    assert "HassTimerStatus" in names


async def test_set_position_requires_exposed_cover(hass: HomeAssistant) -> None:
    """Test HassSetPosition is only exposed when a cover/valve is exposed."""
    assert "HassSetPosition" in await _tool_names(hass)

    async_expose_entity(hass, "conversation", COVER_ENTITY_ID, False)
    assert "HassSetPosition" not in await _tool_names(hass)


async def test_prompt_includes_device_control(hass: HomeAssistant) -> None:
    """Test the platform contributes device-control guidance when exposed."""
    result = intent_llm.async_get_tools(hass, _llm_context(), "assist")
    assert result is not None
    assert result.prompt is not None
    assert intent_llm.DEVICE_CONTROL_TOOL_USAGE_PROMPT in result.prompt
    assert "This device is not able to start timers." in result.prompt


async def test_no_prompt_without_exposed_entities(hass: HomeAssistant) -> None:
    """Test the platform contributes no prompt when nothing is exposed."""
    async_expose_entity(hass, "conversation", COVER_ENTITY_ID, False)
    result = intent_llm.async_get_tools(hass, _llm_context(), "assist")
    assert result is not None
    assert result.prompt is None


async def test_no_tools_for_other_api(hass: HomeAssistant) -> None:
    """Test the platform returns None for an unsupported API."""
    assert intent_llm.async_get_tools(hass, _llm_context(), "other") is None
