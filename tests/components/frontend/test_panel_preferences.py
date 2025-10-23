"""Tests for frontend panel preferences."""

from typing import Any

import pytest

from homeassistant.components.frontend import (
    EVENT_PANELS_UPDATED,
    async_register_built_in_panel,
)
from homeassistant.components.frontend.panel_preferences import (
    DATA_PANEL_PREFERENCES,
    STORAGE_KEY,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_capture_events
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_frontend(hass: HomeAssistant) -> None:
    """Set up the frontend integration."""
    assert await async_setup_component(hass, "frontend", {})
    await hass.async_block_till_done()


async def test_panel_preferences_collection_loaded(hass: HomeAssistant) -> None:
    """Test that panel preferences collection is loaded on setup."""
    assert DATA_PANEL_PREFERENCES in hass.data
    collection = hass.data[DATA_PANEL_PREFERENCES]
    assert collection is not None


async def test_create_panel_preference(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test creating a panel preference."""
    client = await hass_ws_client(hass)

    # Register a test panel
    async_register_built_in_panel(
        hass,
        "test_panel",
        sidebar_title="Test Panel",
        sidebar_icon="mdi:test",
    )

    # Create a panel preference
    await client.send_json_auto_id(
        {
            "type": "frontend/panel_preferences/create",
            "panel_id": "test_panel",
            "show_in_sidebar": False,
        }
    )
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["panel_id"] == "test_panel"
    assert msg["result"]["show_in_sidebar"] is False


async def test_create_panel_preference_without_field_uses_panel_auto_default(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test creating preference without field uses panel's auto-determined default."""
    client = await hass_ws_client(hass)

    # Register a panel with title (auto show_in_sidebar=True)
    async_register_built_in_panel(
        hass,
        "test_panel_auto_true",
        sidebar_title="Test Panel",
        sidebar_icon="mdi:test",
    )

    # Create a panel preference without specifying show_in_sidebar
    await client.send_json_auto_id(
        {
            "type": "frontend/panel_preferences/create",
            "panel_id": "test_panel_auto_true",
        }
    )
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["panel_id"] == "test_panel_auto_true"
    # When not specified, show_in_sidebar should not be in the preference
    assert "show_in_sidebar" not in msg["result"]

    # Get panels - should use panel's auto-determined default (True)
    await client.send_json_auto_id({"type": "get_panels"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["test_panel_auto_true"]["show_in_sidebar"] is True


async def test_update_panel_preference(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test updating a panel preference."""
    client = await hass_ws_client(hass)

    # Create a panel preference
    await client.send_json_auto_id(
        {
            "type": "frontend/panel_preferences/create",
            "panel_id": "test_panel",
            "show_in_sidebar": True,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    item_id = msg["result"]["id"]

    # Update the preference
    await client.send_json_auto_id(
        {
            "type": "frontend/panel_preferences/update",
            "panel_preference_id": item_id,
            "show_in_sidebar": False,
        }
    )
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"]["show_in_sidebar"] is False


async def test_list_panel_preferences(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test listing panel preferences."""
    client = await hass_ws_client(hass)

    # Create two panel preferences
    await client.send_json_auto_id(
        {
            "type": "frontend/panel_preferences/create",
            "panel_id": "panel_1",
            "show_in_sidebar": True,
        }
    )
    await client.receive_json()

    await client.send_json_auto_id(
        {
            "type": "frontend/panel_preferences/create",
            "panel_id": "panel_2",
            "show_in_sidebar": False,
        }
    )
    await client.receive_json()

    # List all preferences
    await client.send_json_auto_id({"type": "frontend/panel_preferences/list"})
    msg = await client.receive_json()

    assert msg["success"]
    assert len(msg["result"]) == 2
    panel_ids = {item["panel_id"] for item in msg["result"]}
    assert panel_ids == {"panel_1", "panel_2"}


async def test_delete_panel_preference(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test deleting a panel preference."""
    client = await hass_ws_client(hass)

    # Create a panel preference
    await client.send_json_auto_id(
        {
            "type": "frontend/panel_preferences/create",
            "panel_id": "test_panel",
            "show_in_sidebar": False,
        }
    )
    msg = await client.receive_json()
    item_id = msg["result"]["id"]

    # Delete the preference
    await client.send_json_auto_id(
        {
            "type": "frontend/panel_preferences/delete",
            "panel_preference_id": item_id,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    # Verify it's deleted
    await client.send_json_auto_id({"type": "frontend/panel_preferences/list"})
    msg = await client.receive_json()
    assert len(msg["result"]) == 0


async def test_get_panels_respects_preferences(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that get_panels respects panel preferences."""
    client = await hass_ws_client(hass)

    # Register a panel with sidebar info
    async_register_built_in_panel(
        hass,
        "test_panel",
        sidebar_title="Test Panel",
        sidebar_icon="mdi:test",
    )

    # Get panels - should show in sidebar by default
    await client.send_json_auto_id({"type": "get_panels"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["test_panel"]["title"] == "Test Panel"
    assert msg["result"]["test_panel"]["icon"] == "mdi:test"
    assert msg["result"]["test_panel"]["show_in_sidebar"] is True

    # Create preference to hide from sidebar
    await client.send_json_auto_id(
        {
            "type": "frontend/panel_preferences/create",
            "panel_id": "test_panel",
            "show_in_sidebar": False,
        }
    )
    await client.receive_json()

    # Get panels again - show_in_sidebar should be False
    await client.send_json_auto_id({"type": "get_panels"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["test_panel"]["title"] == "Test Panel"
    assert msg["result"]["test_panel"]["icon"] == "mdi:test"
    assert msg["result"]["test_panel"]["show_in_sidebar"] is False


async def test_get_panels_no_sidebar_by_default(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that panels without title are not shown in sidebar."""
    client = await hass_ws_client(hass)

    # Register a panel WITHOUT sidebar info
    async_register_built_in_panel(hass, "test_panel_no_sidebar")

    # Get panels - should not show in sidebar by default
    await client.send_json_auto_id({"type": "get_panels"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["test_panel_no_sidebar"]["title"] is None
    assert msg["result"]["test_panel_no_sidebar"]["icon"] is None
    assert msg["result"]["test_panel_no_sidebar"]["show_in_sidebar"] is False


async def test_get_panels_preference_overrides_default(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that user preference can override default sidebar visibility."""
    client = await hass_ws_client(hass)

    # Register a panel WITHOUT sidebar info (default show_in_sidebar=False)
    async_register_built_in_panel(hass, "hidden_panel")

    # Get panels - should not show in sidebar by default
    await client.send_json_auto_id({"type": "get_panels"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["hidden_panel"]["show_in_sidebar"] is False

    # Create preference to show it (even though it has no sidebar info by default)
    await client.send_json_auto_id(
        {
            "type": "frontend/panel_preferences/create",
            "panel_id": "hidden_panel",
            "show_in_sidebar": True,
        }
    )
    await client.receive_json()

    # Get panels - preference is true, so show_in_sidebar should be True
    # (even though panel has no sidebar info)
    await client.send_json_auto_id({"type": "get_panels"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["hidden_panel"]["title"] is None
    assert msg["result"]["hidden_panel"]["icon"] is None
    assert msg["result"]["hidden_panel"]["show_in_sidebar"] is True


async def test_panel_preferences_fire_update_event(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that panel preference changes fire update events."""
    client = await hass_ws_client(hass)
    events = async_capture_events(hass, EVENT_PANELS_UPDATED)

    # Create a preference - should fire event
    await client.send_json_auto_id(
        {
            "type": "frontend/panel_preferences/create",
            "panel_id": "test_panel",
            "show_in_sidebar": False,
        }
    )
    msg = await client.receive_json()
    item_id = msg["result"]["id"]
    await hass.async_block_till_done()
    assert len(events) == 1

    # Update a preference - should fire event
    await client.send_json_auto_id(
        {
            "type": "frontend/panel_preferences/update",
            "panel_preference_id": item_id,
            "show_in_sidebar": True,
        }
    )
    await client.receive_json()
    await hass.async_block_till_done()
    assert len(events) == 2

    # Delete a preference - should fire event
    await client.send_json_auto_id(
        {
            "type": "frontend/panel_preferences/delete",
            "panel_preference_id": item_id,
        }
    )
    await client.receive_json()
    await hass.async_block_till_done()
    assert len(events) == 3


async def test_panel_preferences_storage_persistence(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that panel preferences are persisted to storage."""
    client = await hass_ws_client(hass)

    # Create a panel preference
    await client.send_json_auto_id(
        {
            "type": "frontend/panel_preferences/create",
            "panel_id": "persisted_panel",
            "show_in_sidebar": False,
        }
    )
    await client.receive_json()
    await hass.async_block_till_done()

    # Manually flush the storage
    collection_obj = hass.data[DATA_PANEL_PREFERENCES]
    await collection_obj.store.async_save(collection_obj._data_to_save())

    # Check storage
    assert STORAGE_KEY in hass_storage
    stored_data = hass_storage[STORAGE_KEY]
    assert stored_data["version"] == 1
    items = stored_data["data"]["items"]
    # Items is stored as a list
    assert len(items) == 1
    item = items[0] if isinstance(items, list) else list(items.values())[0]
    assert item["panel_id"] == "persisted_panel"
    assert item["show_in_sidebar"] is False
