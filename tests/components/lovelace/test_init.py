"""Test the Lovelace initialization."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.components import ai_task
from homeassistant.components.lovelace import _validate_url_slug
from homeassistant.components.lovelace.llm import LovelaceDashboardGenerationAPI
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    llm,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


def _llm_context() -> llm.LLMContext:
    """Create an LLM context for tests."""
    return llm.LLMContext(
        platform="test",
        context=None,
        language="en",
        assistant=None,
        device_id=None,
    )


@pytest.fixture
def mock_onboarding_not_done() -> Generator[MagicMock]:
    """Mock that Home Assistant is currently onboarding."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=False,
    ) as mock_onboarding:
        yield mock_onboarding


@pytest.fixture
def mock_onboarding_done() -> Generator[MagicMock]:
    """Mock that Home Assistant is currently onboarding."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=True,
    ) as mock_onboarding:
        yield mock_onboarding


@pytest.fixture
def mock_add_onboarding_listener() -> Generator[MagicMock]:
    """Mock that Home Assistant is currently onboarding."""
    with patch(
        "homeassistant.components.onboarding.async_add_listener",
    ) as mock_add_onboarding_listener:
        yield mock_add_onboarding_listener


async def test_create_dashboards_when_onboarded(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    mock_onboarding_done,
) -> None:
    """Test we don't create dashboards when onboarded."""
    client = await hass_ws_client(hass)

    assert await async_setup_component(hass, "lovelace", {})

    # List dashboards
    await client.send_json_auto_id({"type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []


async def test_create_dashboards_when_not_onboarded(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
    mock_add_onboarding_listener,
    mock_onboarding_not_done,
) -> None:
    """Test we automatically create dashboards when not onboarded."""
    client = await hass_ws_client(hass)

    assert await async_setup_component(hass, "lovelace", {})

    # Call onboarding listener
    mock_add_onboarding_listener.mock_calls[0][1][1]()
    await hass.async_block_till_done()

    # List dashboards
    await client.send_json_auto_id({"type": "lovelace/dashboards/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "icon": "mdi:map",
            "id": "map",
            "mode": "storage",
            "require_admin": False,
            "show_in_sidebar": True,
            "title": "Map",
            "url_path": "map",
        }
    ]

    # List map dashboard config
    await client.send_json_auto_id({"type": "lovelace/config", "url_path": "map"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"strategy": {"type": "map"}}


async def test_generate_dashboard_with_ai(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_onboarding_done,
) -> None:
    """Test generating a dashboard with AI over websocket."""
    hass.config.components.add(ai_task.DOMAIN)
    assert await async_setup_component(hass, "lovelace", {})

    client = await hass_ws_client(hass)
    generated_config = {"views": [{"title": "Home", "cards": []}]}

    with patch(
        "homeassistant.components.lovelace.websocket.ai_task.async_generate_data",
        return_value=ai_task.GenDataTaskResult(
            conversation_id="conversation-1",
            data=generated_config,
        ),
    ) as mock_generate:
        await client.send_json_auto_id(
            {"type": "lovelace/config/generate", "prompt": "Create a lights dashboard"}
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "conversation_id": "conversation-1",
        "config": generated_config,
    }

    kwargs = mock_generate.call_args.kwargs
    assert kwargs["task_name"] == "lovelace_dashboard_generation"
    assert "Create a lights dashboard" in kwargs["instructions"]
    assert isinstance(kwargs["llm_api"], LovelaceDashboardGenerationAPI)


async def test_generate_dashboard_with_ai_invalid_response(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_onboarding_done,
) -> None:
    """Test generating a dashboard fails when model returns invalid config."""
    hass.config.components.add(ai_task.DOMAIN)
    assert await async_setup_component(hass, "lovelace", {})

    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.lovelace.websocket.ai_task.async_generate_data",
        return_value=ai_task.GenDataTaskResult(
            conversation_id="conversation-1",
            data={"title": "Broken"},
        ),
    ):
        await client.send_json_auto_id(
            {"type": "lovelace/config/generate", "prompt": "Broken dashboard"}
        )
        response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "error"
    assert "at least one view" in response["error"]["message"]


async def test_generate_dashboard_with_ai_json_markdown(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_onboarding_done,
) -> None:
    """Test generating a dashboard when model returns JSON in markdown."""
    hass.config.components.add(ai_task.DOMAIN)
    assert await async_setup_component(hass, "lovelace", {})

    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.lovelace.websocket.ai_task.async_generate_data",
        return_value=ai_task.GenDataTaskResult(
            conversation_id="conversation-1",
            data='```json\n{"views":[{"title":"Home"}]}\n```',
        ),
    ):
        await client.send_json_auto_id(
            {"type": "lovelace/config/generate", "prompt": "Markdown dashboard"}
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"]["config"] == {"views": [{"title": "Home"}]}


async def test_lovelace_generation_list_tools_match_hab(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test list tool behavior matches Home Assistant Builder list commands."""
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    floor_1 = floor_registry.async_create("First floor")
    floor_2 = floor_registry.async_create("Second floor")
    kitchen = area_registry.async_create("Kitchen", floor_id=floor_1.floor_id)
    bedroom = area_registry.async_create("Bedroom", floor_id=floor_2.floor_id)

    device_kitchen = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "kitchen_device")},
        name="Kitchen Device",
        manufacturer="Acme",
        model="M1",
    )
    device_registry.async_update_device(device_kitchen.id, area_id=kitchen.id)

    device_bedroom = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "bedroom_device")},
        name="Bedroom Device",
        manufacturer="Acme",
        model="M2",
    )
    device_registry.async_update_device(device_bedroom.id, area_id=bedroom.id)

    kitchen_entry = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "kitchen_temperature",
        device_id=device_kitchen.id,
        original_device_class="temperature",
    )
    entity_registry.async_update_entity(
        kitchen_entry.entity_id, area_id=kitchen.id, labels={"important"}
    )

    bedroom_entry = entity_registry.async_get_or_create(
        "binary_sensor",
        "test",
        "bedroom_motion",
        device_id=device_bedroom.id,
        original_device_class="motion",
    )
    entity_registry.async_update_entity(bedroom_entry.entity_id, area_id=bedroom.id)

    hass.states.async_set(
        kitchen_entry.entity_id, "21", {"friendly_name": "Kitchen Temp"}
    )
    hass.states.async_set(
        bedroom_entry.entity_id, "off", {"friendly_name": "Bedroom Motion"}
    )

    api = LovelaceDashboardGenerationAPI(hass)
    api_instance = await api.async_get_api_instance(_llm_context())
    tools = {tool.name: tool for tool in api_instance.tools}

    assert sorted(tools) == ["area_list", "device_list", "entity_list"]

    area_result = await tools["area_list"].async_call(
        hass,
        llm.ToolInput(
            tool_name="area_list",
            tool_args={"floor": floor_1.floor_id, "brief": True},
        ),
        _llm_context(),
    )
    assert area_result == {"areas": [{"area_id": kitchen.id, "name": "Kitchen"}]}

    device_result = await tools["device_list"].async_call(
        hass,
        llm.ToolInput(
            tool_name="device_list",
            tool_args={"area": kitchen.id, "brief": True},
        ),
        _llm_context(),
    )
    assert device_result == {
        "devices": [{"id": device_kitchen.id, "name": "Kitchen Device"}]
    }

    entity_result = await tools["entity_list"].async_call(
        hass,
        llm.ToolInput(
            tool_name="entity_list",
            tool_args={
                "domain": "sensor",
                "device-class": "temperature",
                "label": "important",
                "brief": True,
            },
        ),
        _llm_context(),
    )
    assert entity_result == {
        "entities": [{"entity_id": kitchen_entry.entity_id, "name": "Kitchen Temp"}]
    }

    entity_count = await tools["entity_list"].async_call(
        hass,
        llm.ToolInput(
            tool_name="entity_list",
            tool_args={"device": device_kitchen.id, "count": True},
        ),
        _llm_context(),
    )
    assert entity_count == {"count": 1}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("lovelace", "lovelace"),
        ("my-dashboard", "my-dashboard"),
        ("my-cool-dashboard", "my-cool-dashboard"),
    ],
)
def test_validate_url_slug_valid(value: str, expected: str) -> None:
    """Test _validate_url_slug with valid values."""
    assert _validate_url_slug(value) == expected


@pytest.mark.parametrize(
    ("value", "error_message"),
    [
        (None, r"Slug should not be None"),
        ("nodash", r"Url path needs to contain a hyphen \(-\)"),
        ("my-dash board", r"invalid slug my-dash board \(try my-dash-board\)"),
    ],
)
def test_validate_url_slug_invalid(value: Any, error_message: str) -> None:
    """Test _validate_url_slug with invalid values."""
    with pytest.raises(vol.Invalid, match=error_message):
        _validate_url_slug(value)
