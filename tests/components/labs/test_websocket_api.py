"""Tests for the Home Assistant Labs WebSocket API."""

from __future__ import annotations

from typing import Any
from unittest.mock import ANY, AsyncMock, patch

from homeassistant.components.labs import EVENT_LABS_UPDATED, async_setup
from homeassistant.components.labs.const import LABS_DATA
from homeassistant.core import HomeAssistant

from tests.common import MockUser
from tests.typing import WebSocketGenerator


async def test_websocket_list_features_no_integration(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing features when required integration is not loaded."""
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "labs/list"})
    msg = await client.receive_json()

    assert msg["success"]
    # No features because kitchen_sink integration is not loaded
    assert msg["result"] == {"features": []}


async def test_websocket_list_features_with_integration(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing features when required integration is loaded."""
    # Load kitchen_sink integration first
    hass.config.components.add("kitchen_sink")

    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "labs/list"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "features": [
            {
                "feature": "special_repair",
                "domain": "kitchen_sink",
                "enabled": False,
                "feedback_url": ANY,
                "learn_more_url": ANY,
                "report_issue_url": ANY,
            }
        ]
    }


async def test_websocket_list_features_with_enabled_feature(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test listing features with one enabled."""
    hass_storage["core.labs"] = {
        "version": 1,
        "data": {"features": {"kitchen_sink.special_repair": True}},
    }

    # Load kitchen_sink integration first
    hass.config.components.add("kitchen_sink")

    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "labs/list"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "features": [
            {
                "feature": "special_repair",
                "domain": "kitchen_sink",
                "enabled": True,
                "feedback_url": ANY,
                "learn_more_url": ANY,
                "report_issue_url": ANY,
            }
        ]
    }


async def test_websocket_update_feature_enable(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test enabling a feature via WebSocket."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Track events
    events = []

    def event_listener(event):
        events.append(event)

    hass.bus.async_listen(EVENT_LABS_UPDATED, event_listener)

    # Enable the feature
    await client.send_json(
        {
            "id": 1,
            "type": "labs/update",
            "feature_id": "kitchen_sink.special_repair",
            "enabled": True,
        }
    )
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] is None

    # Verify event was fired
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["feature_id"] == "kitchen_sink.special_repair"
    assert events[0].data["enabled"] is True

    # Verify storage was updated
    store = hass.data[LABS_DATA].store
    data = await store.async_load()
    assert data["features"]["kitchen_sink.special_repair"] is True


async def test_websocket_update_feature_disable(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test disabling a feature via WebSocket."""
    # Pre-populate storage with enabled feature
    hass_storage["core.labs"] = {
        "version": 1,
        "minor_version": 1,
        "key": "core.labs",
        "data": {"features": {"kitchen_sink.special_repair": True}},
    }

    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Track events
    events = []

    def event_listener(event):
        events.append(event)

    hass.bus.async_listen(EVENT_LABS_UPDATED, event_listener)

    # Disable the feature
    await client.send_json(
        {
            "id": 1,
            "type": "labs/update",
            "feature_id": "kitchen_sink.special_repair",
            "enabled": False,
        }
    )
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] is None

    # Verify event was fired
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["feature_id"] == "kitchen_sink.special_repair"
    assert events[0].data["enabled"] is False

    # Verify storage was updated
    store = hass.data[LABS_DATA].store
    data = await store.async_load()
    assert data["features"]["kitchen_sink.special_repair"] is False


async def test_websocket_update_nonexistent_feature(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test updating a feature that doesn't exist."""
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "labs/update",
            "feature_id": "nonexistent_feature",
            "enabled": True,
        }
    )
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"
    assert "not found" in msg["error"]["message"].lower()


async def test_websocket_update_unavailable_feature(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test updating a feature whose integration is not loaded still works."""
    # Don't load kitchen_sink integration
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Feature is pre-loaded, so update succeeds even though integration isn't loaded
    await client.send_json(
        {
            "id": 1,
            "type": "labs/update",
            "feature_id": "kitchen_sink.special_repair",
            "enabled": True,
        }
    )
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] is None


async def test_websocket_list_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test that listing features requires admin privileges."""
    # Remove admin privileges
    hass_admin_user.groups = []

    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "labs/list"})
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"


async def test_websocket_update_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test that updating features requires admin privileges."""
    # Remove admin privileges
    hass_admin_user.groups = []

    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "labs/update",
            "feature_id": "kitchen_sink.special_repair",
            "enabled": True,
        }
    )
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"


async def test_websocket_update_validates_enabled_parameter(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that enabled parameter must be boolean."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Try with string instead of boolean
    await client.send_json(
        {
            "id": 1,
            "type": "labs/update",
            "feature_id": "kitchen_sink.special_repair",
            "enabled": "true",
        }
    )
    msg = await client.receive_json()

    assert not msg["success"]
    # Validation error from voluptuous


async def test_multiple_features_list(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test listing multiple features if they exist."""
    # Load demo to get features
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "labs/list"})
    msg = await client.receive_json()

    assert msg["success"]
    assert "features" in msg["result"]
    assert isinstance(msg["result"]["features"], list)
    # At least one feature from kitchen_sink
    assert len(msg["result"]["features"]) >= 1


async def test_storage_persists_across_calls(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that storage persists feature state across multiple calls."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Enable feature
    await client.send_json(
        {
            "id": 1,
            "type": "labs/update",
            "feature_id": "kitchen_sink.special_repair",
            "enabled": True,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    # List features - should show enabled
    await client.send_json({"id": 2, "type": "labs/list"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["features"][0]["enabled"] is True

    # Disable feature
    await client.send_json(
        {
            "id": 3,
            "type": "labs/update",
            "feature_id": "kitchen_sink.special_repair",
            "enabled": False,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    # List features - should show disabled
    await client.send_json({"id": 4, "type": "labs/list"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["features"][0]["enabled"] is False


async def test_feature_urls_present(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that features include feedback and report URLs."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "labs/list"})
    msg = await client.receive_json()

    assert msg["success"]
    feature = msg["result"]["features"][0]
    assert "feedback_url" in feature
    assert "learn_more_url" in feature
    assert "report_issue_url" in feature
    assert feature["feedback_url"] is not None
    assert feature["learn_more_url"] is not None
    assert feature["report_issue_url"] is not None


async def test_websocket_update_toggle_multiple_times(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test toggling a feature multiple times in succession."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Enable
    await client.send_json(
        {
            "id": 1,
            "type": "labs/update",
            "feature_id": "kitchen_sink.special_repair",
            "enabled": True,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    # Enable again (should still work)
    await client.send_json(
        {
            "id": 2,
            "type": "labs/update",
            "feature_id": "kitchen_sink.special_repair",
            "enabled": True,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    # Disable
    await client.send_json(
        {
            "id": 3,
            "type": "labs/update",
            "feature_id": "kitchen_sink.special_repair",
            "enabled": False,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    # Disable again
    await client.send_json(
        {
            "id": 4,
            "type": "labs/update",
            "feature_id": "kitchen_sink.special_repair",
            "enabled": False,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]


async def test_websocket_update_with_backup(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test enabling a feature with backup creation."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Mock the backup manager
    mock_backup_manager = AsyncMock()
    mock_backup_manager.async_create_automatic_backup = AsyncMock()

    with patch(
        "homeassistant.components.labs.async_get_manager",
        return_value=mock_backup_manager,
    ):
        # Enable with backup
        await client.send_json(
            {
                "id": 1,
                "type": "labs/update",
                "feature_id": "kitchen_sink.special_repair",
                "enabled": True,
                "create_backup": True,
            }
        )
        msg = await client.receive_json()

    assert msg["success"]
    # Verify backup was created
    mock_backup_manager.async_create_automatic_backup.assert_called_once()


async def test_websocket_update_with_backup_failure(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that backup failure prevents feature enable."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Mock the backup manager to fail
    mock_backup_manager = AsyncMock()
    mock_backup_manager.async_create_automatic_backup = AsyncMock(
        side_effect=Exception("Backup failed")
    )

    with patch(
        "homeassistant.components.labs.async_get_manager",
        return_value=mock_backup_manager,
    ):
        # Try to enable with backup (should fail)
        await client.send_json(
            {
                "id": 1,
                "type": "labs/update",
                "feature_id": "kitchen_sink.special_repair",
                "enabled": True,
                "create_backup": True,
            }
        )
        msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "unknown_error"
    assert "backup" in msg["error"]["message"].lower()

    # Verify feature was NOT enabled
    store = hass.data[LABS_DATA].store
    data = await store.async_load()
    assert data["features"].get("kitchen_sink.special_repair") is not True


async def test_websocket_update_disable_ignores_backup(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that disabling ignores the backup parameter."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Mock the backup manager (should not be called)
    mock_backup_manager = AsyncMock()
    mock_backup_manager.async_create_automatic_backup = AsyncMock()

    with patch(
        "homeassistant.components.labs.async_get_manager",
        return_value=mock_backup_manager,
    ):
        # Disable with backup flag (backup should be ignored)
        await client.send_json(
            {
                "id": 1,
                "type": "labs/update",
                "feature_id": "kitchen_sink.special_repair",
                "enabled": False,
                "create_backup": True,
            }
        )
        msg = await client.receive_json()

    assert msg["success"]
    # Verify backup was NOT created
    mock_backup_manager.async_create_automatic_backup.assert_not_called()
