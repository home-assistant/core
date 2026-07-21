"""Tests for the homeassistant LLM tools platform."""

import pytest
from syrupy.assertion import SnapshotAssertion
from voluptuous_openapi import convert

from homeassistant.components import llm as llm_component
from homeassistant.components.homeassistant import llm as ha_llm
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.homeassistant.llm import async_get_exposed_entities
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    llm,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

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
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    assert "GetLiveContext" in [tool.name for tool in result.tools]


async def test_no_tools_for_other_api(hass: HomeAssistant) -> None:
    """Test the platform returns None for an unsupported API."""
    assert ha_llm.async_get_tools(hass, _llm_context(), "other") is None


async def test_prompt_includes_context(hass: HomeAssistant) -> None:
    """Test the platform contributes the live-context and static-overview prompt."""
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    assert result.prompt is not None
    assert ha_llm.DYNAMIC_CONTEXT_PROMPT in result.prompt
    assert "Static Context:" in result.prompt
    assert "Kitchen Light" in result.prompt


async def test_prompt_no_entities(hass: HomeAssistant) -> None:
    """Test the platform contributes the no-entities prompt when nothing is exposed."""
    async_expose_entity(hass, "conversation", ENTITY_ID, False)
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    assert result.prompt == ha_llm.NO_ENTITIES_PROMPT


async def test_get_live_context_no_exposed_entities(hass: HomeAssistant) -> None:
    """Test GetLiveContext reports an error when nothing is exposed."""
    async_expose_entity(hass, "conversation", ENTITY_ID, False)
    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context, "assist")
    tool = next(tool for tool in result.tools if tool.name == "GetLiveContext")

    response = await tool.async_call(
        hass, llm.ToolInput("GetLiveContext", {}), llm_context
    )
    assert response == {"success": False, "error": ha_llm.NO_ENTITIES_PROMPT}


async def test_get_live_context_tool(hass: HomeAssistant) -> None:
    """Test GetLiveContext returns exposed entity state."""
    llm_context = _llm_context()
    result = await llm_component.async_get_tools(hass, llm_context, "assist")
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


async def test_get_live_context_tool_filter(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test the filter parameters of the GetLiveContext tool."""
    # The autouse fixture exposes light.kitchen; drop it for a clean entity set.
    async_expose_entity(hass, "conversation", ENTITY_ID, False)
    assert await async_setup_component(hass, "intent", {})

    llm_context = _llm_context()

    entry = MockConfigEntry(title=None)
    entry.add_to_hass(hass)

    office = area_registry.async_create("Office")
    area_registry.async_update(office.id, aliases={"Workspace"})
    area_registry.async_create("Kitchen")

    office_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("test", "office-1")},
        suggested_area="Office",
    )
    kitchen_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={("test", "kitchen-1")},
        suggested_area="Kitchen",
    )

    office_light = entity_registry.async_get_or_create(
        "light",
        "test",
        "office_light",
        original_name="Office Light",
        device_id=office_device.id,
        suggested_object_id="office_light",
    )
    kitchen_light = entity_registry.async_get_or_create(
        "light",
        "test",
        "kitchen_light",
        original_name="Kitchen Light",
        device_id=kitchen_device.id,
        suggested_object_id="kitchen_light",
    )
    office_switch = entity_registry.async_get_or_create(
        "switch",
        "test",
        "office_switch",
        original_name="Office Switch",
        device_id=office_device.id,
        suggested_object_id="office_switch",
    )
    front_door = entity_registry.async_get_or_create(
        "lock",
        "test",
        "front_door",
        original_name="Front Door",
        suggested_object_id="front_door",
    )
    # Two entities sharing the same name in different areas
    office_ac = entity_registry.async_get_or_create(
        "climate",
        "test",
        "office_ac",
        original_name="AC",
        device_id=office_device.id,
        suggested_object_id="office_ac",
    )
    kitchen_ac = entity_registry.async_get_or_create(
        "climate",
        "test",
        "kitchen_ac",
        original_name="AC",
        device_id=kitchen_device.id,
        suggested_object_id="kitchen_ac",
    )
    entity_registry.async_update_entity(
        kitchen_light.entity_id, aliases=[er.COMPUTED_NAME, "Cooking Lamp"]
    )

    for entity_id in (
        office_light.entity_id,
        kitchen_light.entity_id,
        office_switch.entity_id,
        front_door.entity_id,
        office_ac.entity_id,
        kitchen_ac.entity_id,
    ):
        async_expose_entity(hass, "conversation", entity_id, True)

    hass.states.async_set(office_light.entity_id, "on")
    hass.states.async_set(kitchen_light.entity_id, "off")
    hass.states.async_set(office_switch.entity_id, "on")
    hass.states.async_set(front_door.entity_id, "locked")
    hass.states.async_set(office_ac.entity_id, "cool")
    hass.states.async_set(kitchen_ac.entity_id, "heat")

    await hass.async_block_till_done()
    tools = await llm_component.async_get_tools(hass, llm_context, "assist")
    tool = next(t for t in tools.tools if t.name == "GetLiveContext")

    async def _get_live_context(tool_args: dict) -> dict:
        return await tool.async_call(
            hass, llm.ToolInput("GetLiveContext", tool_args), llm_context
        )

    # Filter by area and domain (example 1)
    result = await _get_live_context({"area": "Office", "domain": "light"})
    assert result["success"] is True
    assert "Office Light" in result["result"]
    assert "Kitchen Light" not in result["result"]
    assert "Office Switch" not in result["result"]
    assert "Front Door" not in result["result"]

    # Filter by name (example 2)
    result = await _get_live_context({"name": "Front Door"})
    assert result["success"] is True
    assert "Front Door" in result["result"]
    assert "Office Light" not in result["result"]
    assert "Kitchen Light" not in result["result"]
    assert "Office Switch" not in result["result"]

    # Name filter is case insensitive
    result = await _get_live_context({"name": "front door"})
    assert result["success"] is True
    assert "Front Door" in result["result"]

    # Area filter matches area aliases
    result = await _get_live_context({"area": "workspace"})
    assert result["success"] is True
    assert "Office Light" in result["result"]
    assert "Office Switch" in result["result"]
    assert "Kitchen Light" not in result["result"]
    assert "Front Door" not in result["result"]

    # Domain filter accepts a list
    result = await _get_live_context({"domain": ["switch", "lock"]})
    assert result["success"] is True
    assert "Office Switch" in result["result"]
    assert "Front Door" in result["result"]
    assert "Office Light" not in result["result"]
    assert "Kitchen Light" not in result["result"]

    # Domain filter is case insensitive
    result = await _get_live_context({"domain": "Light"})
    assert result["success"] is True
    assert "Office Light" in result["result"]
    assert "Kitchen Light" in result["result"]
    assert "Office Switch" not in result["result"]
    assert "Front Door" not in result["result"]

    # No filters returns all exposed entities
    result = await _get_live_context({})
    assert result["success"] is True
    assert "Office Light" in result["result"]
    assert "Kitchen Light" in result["result"]
    assert "Office Switch" in result["result"]
    assert "Front Door" in result["result"]

    # Filter that matches nothing returns a descriptive error
    result = await _get_live_context({"name": "Does Not Exist"})
    assert result == {
        "success": False,
        "error": "No exposed entities matched name 'Does Not Exist'",
    }

    # Name filter strips surrounding whitespace
    result = await _get_live_context({"name": "  Front Door  "})
    assert result["success"] is True
    assert "Front Door" in result["result"]

    # Area filter strips surrounding whitespace
    result = await _get_live_context({"area": "  Office  "})
    assert result["success"] is True
    assert "Office Light" in result["result"]
    assert "Office Switch" in result["result"]
    assert "Kitchen Light" not in result["result"]

    # Name filter accepts entity_id
    result = await _get_live_context({"name": office_light.entity_id})
    assert result["success"] is True
    assert "Office Light" in result["result"]
    assert "Kitchen Light" not in result["result"]
    assert "Office Switch" not in result["result"]

    # Area filter accepts area_id
    result = await _get_live_context({"area": office.id})
    assert result["success"] is True
    assert "Office Light" in result["result"]
    assert "Office Switch" in result["result"]
    assert "Kitchen Light" not in result["result"]
    assert "Front Door" not in result["result"]

    # Name filter matches entity aliases
    result = await _get_live_context({"name": "cooking lamp"})
    assert result["success"] is True
    assert "Kitchen Light" in result["result"]
    assert "Office Light" not in result["result"]

    # Combining name + area narrows the result
    result = await _get_live_context({"name": "Office Light", "area": "Office"})
    assert result["success"] is True
    assert "Office Light" in result["result"]
    assert "Office Switch" not in result["result"]

    # Combining name + area returns the failing constraint in the error
    result = await _get_live_context({"name": "Office Light", "area": "Kitchen"})
    assert result == {
        "success": False,
        "error": "No exposed entities found in area 'Kitchen'",
    }

    # Unknown area distinguishes "invalid area" from "no entities in area"
    result = await _get_live_context({"area": "Garage"})
    assert result == {
        "success": False,
        "error": "Area 'Garage' does not exist",
    }

    # Unknown domain reports which domain(s) failed
    result = await _get_live_context({"domain": "fan"})
    assert result == {
        "success": False,
        "error": "No exposed entities found in domain(s): fan",
    }

    # Entities sharing a name are all returned rather than failing as an
    # ambiguous match, since this tool only returns context.
    result = await _get_live_context({"name": "AC"})
    assert result["success"] is True
    assert result["result"].count("domain: climate") == 2
    assert "Office" in result["result"]
    assert "Kitchen" in result["result"]

    # Combining a shared name with an area narrows to the single match
    result = await _get_live_context({"name": "AC", "area": "Kitchen"})
    assert result["success"] is True
    assert result["result"].count("domain: climate") == 1
    assert "Kitchen" in result["result"]
    assert "Office" not in result["result"]


async def test_get_live_context_schema(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test that GetLiveContext tool parameters convert to a sane OpenAPI schema."""
    result = await llm_component.async_get_tools(hass, _llm_context(), "assist")
    tool = next(t for t in result.tools if t.name == "GetLiveContext")

    api = await llm.async_get_api(hass, "assist", _llm_context())
    schema = convert(tool.parameters, custom_serializer=api.custom_serializer)

    assert schema == snapshot
