"""Tests for the search LLM tools."""

import probatio
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.search import DOMAIN
from homeassistant.components.search.llm import SearchTool, async_get_tools
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
    llm,
)
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonObjectType, JsonValueType

from tests.common import MockConfigEntry, MockUser


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
async def setup_items(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> dict[str, str]:
    """Set up items of every type to search.

    Returns a stable placeholder for each random device ID.
    """
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "kitchen_lights",
                    "alias": "Kitchen lights",
                    "triggers": {"trigger": "event", "event_type": "test"},
                    "actions": [],
                },
            ]
        },
    )
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "morning_news": {"alias": "Play news", "sequence": []},
            }
        },
    )
    assert await async_setup_component(
        hass,
        "scene",
        {"scene": [{"name": "Kitchen cooking", "entities": {"light.kitchen_1": "on"}}]},
    )

    area_registry.async_create("Kitchen", aliases={"Cooking room"})
    area_registry.async_create("Living room")
    label_registry.async_create("Kitchen appliances")

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    sensor_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "sensor")},
        name="Kitchen sensor",
        manufacturer="Acme",
        model="Multisensor",
    )
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "sensor-speaker")},
        parent_device_id=sensor_device.id,
        name="Kitchen speaker",
    )
    renamed_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "hub")},
        name="Hub",
        manufacturer="Acme",
        model="Kitchen hub",
    )
    device_registry.async_update_device(renamed_device.id, name_by_user="Main hub")
    disabled_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "disabled")},
        name="Kitchen disabled",
    )
    device_registry.async_update_device(
        disabled_device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )

    for index in range(1, 7):
        hass.states.async_set(
            f"light.kitchen_{index}", "on", {ATTR_FRIENDLY_NAME: f"Kitchen {index}"}
        )
    hass.states.async_set("sensor.kitchen", "21", {ATTR_FRIENDLY_NAME: "Kitchen"})
    lamp = entity_registry.async_get_or_create(
        "light", "test", "lamp", suggested_object_id="lamp"
    )
    entity_registry.async_update_entity(lamp.entity_id, aliases=["Counter light"])
    hass.states.async_set(lamp.entity_id, "off", {ATTR_FRIENDLY_NAME: "Lamp"})

    return {
        sensor_device.id: "<sensor device>",
        child_device.id: "<child device>",
        renamed_device.id: "<hub device>",
    }


def _ordered(data: JsonObjectType, device_ids: dict[str, str]) -> JsonValueType:
    """Return the result groups with results as ordered pairs and stable IDs.

    The snapshot serializer sorts dict keys, so pairs keep the result order.
    """
    return {
        key: {
            "total": group["total"],
            "results": [
                [device_ids.get(item_id, item_id), name]
                for item_id, name in group["results"].items()
            ],
        }
        if isinstance(group, dict)
        else group
        for key, group in data.items()
    }


async def test_async_get_tools(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test the search tool is only provided for the Home Assistant API."""
    assert async_get_tools(hass, llm_context, llm.LLM_API_ASSIST) is None

    home_assistant_tools = async_get_tools(
        hass, llm_context, llm.LLM_API_HOME_ASSISTANT
    )
    assert home_assistant_tools is not None
    assert [tool.name for tool in home_assistant_tools.tools] == ["search__search"]


def test_parameters_openapi(snapshot: SnapshotAssertion) -> None:
    """Test that the tool schema can be exported for LLM clients."""
    assert probatio.to_openapi(SearchTool.parameters) == snapshot


@pytest.mark.parametrize(
    "tool_args",
    [
        pytest.param({"query": "kitchen"}, id="all_types"),
        pytest.param({"query": "KITCHEN", "type": "entity"}, id="one_type"),
        pytest.param({"query": "kitchen", "type": "entity", "offset": 5}, id="offset"),
        pytest.param({"query": "kitchen", "type": "device"}, id="device_model"),
        pytest.param({"query": "acme", "type": "device"}, id="device_manufacturer"),
        pytest.param({"query": "cooking", "type": "area"}, id="area_alias"),
        pytest.param({"query": "counter"}, id="entity_alias"),
        pytest.param({"query": "kitchen_lights"}, id="entity_id"),
        pytest.param({"query": "nothing"}, id="no_match"),
    ],
)
async def test_search(
    hass: HomeAssistant,
    llm_context: llm.LLMContext,
    snapshot: SnapshotAssertion,
    setup_items: dict[str, str],
    tool_args: JsonObjectType,
) -> None:
    """Test searching across types."""
    tool = SearchTool()
    result = await tool.async_call(
        hass, llm.ToolInput(tool.name, tool_args), llm_context
    )
    assert result.error is False
    assert _ordered(result.data, setup_items) == snapshot


async def test_offset_without_type(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test an offset requires a type."""
    tool = SearchTool()
    result = await tool.async_call(
        hass, llm.ToolInput(tool.name, {"query": "kitchen", "offset": 5}), llm_context
    )
    assert result == llm.ToolResult(
        data={"error": "Set type to get more results of that type."}, error=True
    )


@pytest.mark.parametrize(
    "tool_args",
    [
        pytest.param({}, id="missing_query"),
        pytest.param({"query": ""}, id="empty_query"),
        pytest.param({"query": "kitchen", "type": "floor"}, id="unknown_type"),
        pytest.param({"query": "kitchen", "offset": -1}, id="negative_offset"),
    ],
)
async def test_invalid_parameters(
    hass: HomeAssistant, llm_context: llm.LLMContext, tool_args: JsonObjectType
) -> None:
    """Test invalid arguments are rejected by the schema."""
    tool = SearchTool()
    with pytest.raises(probatio.Invalid):
        await tool.async_call(hass, llm.ToolInput(tool.name, tool_args), llm_context)


async def test_call_through_api(
    hass: HomeAssistant, hass_admin_user: MockUser, llm_context: llm.LLMContext
) -> None:
    """Test the tool is available through the Home Assistant API."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, "llm", {})
    llm_context.context = Context(user_id=hass_admin_user.id)

    api = await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)
    tool = next(tool for tool in api.tools if tool.name == "search__search")
    assert tool.integration == DOMAIN
    assert tool.annotations == llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    assert await api.async_call_tool(
        llm.ToolInput(tool.name, {"query": "kitchen"})
    ) == llm.ToolResult(data={})
