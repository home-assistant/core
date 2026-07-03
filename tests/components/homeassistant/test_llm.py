"""Tests for the homeassistant LLM tools platform."""

import pytest

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.homeassistant.llm import async_get_exposed_entities
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

ENTITY_ID = "light.kitchen"


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant) -> None:
    """Set up the integrations and expose an entity."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "llm", {})
    hass.states.async_set(ENTITY_ID, "on", {"friendly_name": "Kitchen Light"})
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


async def test_live_context_always_offered(hass: HomeAssistant) -> None:
    """Test GetLiveContext is offered even when nothing is exposed."""
    async_expose_entity(hass, "conversation", ENTITY_ID, False)
    result = await llm_component.async_get_tools(hass, _llm_context())
    assert [tool.name for tool in result.tools] == ["GetLiveContext"]


async def test_get_live_context_tool(hass: HomeAssistant) -> None:
    """Test GetLiveContext returns exposed entity state."""
    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context)
    tool = next((tool for tool in result.tools if tool.name == "GetLiveContext"), None)
    assert tool is not None

    response = await tool.async_call(
        hass, llm.ToolInput("GetLiveContext", {}), llm_context
    )
    assert response["success"] is True
    assert "Kitchen Light" in response["result"]


async def test_get_exposed_entities_timestamp_conversion(hass: HomeAssistant) -> None:
    """Test that async_get_exposed_entities converts timestamp states to local time."""
    # Set the timezone to something other than UTC to ensure conversion is tested
    await hass.config.async_set_time_zone("America/New_York")

    # Set up a timestamp sensor with UTC time
    hass.states.async_set(
        "sensor.test_timestamp",
        "2024-01-15T10:30:00+00:00",
        {"device_class": "timestamp", "friendly_name": "Test Timestamp"},
    )
    # Also test with a non-timestamp sensor to ensure it's not affected
    hass.states.async_set(
        "sensor.regular_sensor",
        "2024-01-15T10:30:00+00:00",
        {"friendly_name": "Regular Sensor"},  # No device_class
    )
    # And test with invalid/empty timestamp
    hass.states.async_set(
        "sensor.invalid_timestamp",
        "not-a-timestamp",
        {"device_class": "timestamp", "friendly_name": "Invalid Timestamp"},
    )
    hass.states.async_set(
        "sensor.empty_timestamp",
        "",
        {"device_class": "timestamp", "friendly_name": "Empty Timestamp"},
    )
    for entity_id in (
        "sensor.test_timestamp",
        "sensor.regular_sensor",
        "sensor.invalid_timestamp",
        "sensor.empty_timestamp",
    ):
        async_expose_entity(hass, "conversation", entity_id, True)

    exposed = async_get_exposed_entities(hass, "conversation", include_state=True)

    # Timestamp state is converted to local time
    assert exposed["sensor.test_timestamp"]["state"] == "2024-01-15T05:30:00-05:00"
    # Regular sensor without device_class keeps its original value
    assert exposed["sensor.regular_sensor"]["state"] == "2024-01-15T10:30:00+00:00"
    # Invalid timestamp remains as-is
    assert exposed["sensor.invalid_timestamp"]["state"] == "not-a-timestamp"
    # Empty timestamp remains empty
    assert exposed["sensor.empty_timestamp"]["state"] == ""

    # With include_state=False no state (and therefore no conversion) is included
    exposed_no_state = async_get_exposed_entities(
        hass, "conversation", include_state=False
    )
    assert "state" not in exposed_no_state["sensor.test_timestamp"]
