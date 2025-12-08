"""Tests for the Home Assistant Labs WebSocket API."""

from __future__ import annotations

from typing import Any
from unittest.mock import ANY, AsyncMock, patch

import pytest

from homeassistant.components.labs import (
    EVENT_LABS_UPDATED,
    async_is_preview_feature_enabled,
    async_setup,
)
from homeassistant.core import HomeAssistant

from . import assert_stored_labs_data

from tests.common import MockUser
from tests.typing import WebSocketGenerator


@pytest.mark.parametrize(
    ("load_integration", "expected_features"),
    [
        (False, []),  # No integration loaded
        (
            True,  # Integration loaded
            [
                {
                    "preview_feature": "special_repair",
                    "domain": "kitchen_sink",
                    "enabled": False,
                    "is_built_in": True,
                    "feedback_url": ANY,
                    "learn_more_url": ANY,
                    "report_issue_url": ANY,
                }
            ],
        ),
    ],
)
async def test_websocket_list_preview_features(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    load_integration: bool,
    expected_features: list,
) -> None:
    """Test listing preview features with different integration states."""
    if load_integration:
        hass.config.components.add("kitchen_sink")

    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "labs/list"})
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {"features": expected_features}


async def test_websocket_update_preview_feature_enable(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test enabling a preview feature via WebSocket."""
    # Load kitchen_sink integration
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    assert "core.labs" not in hass_storage

    # Track events
    events = []

    def event_listener(event):
        events.append(event)

    hass.bus.async_listen(EVENT_LABS_UPDATED, event_listener)

    # Enable the preview feature
    await client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": True,
        }
    )
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] is None

    # Verify event was fired
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["domain"] == "kitchen_sink"
    assert events[0].data["preview_feature"] == "special_repair"
    assert events[0].data["enabled"] is True

    # Verify feature is now enabled
    assert async_is_preview_feature_enabled(hass, "kitchen_sink", "special_repair")

    assert_stored_labs_data(
        hass_storage,
        [{"domain": "kitchen_sink", "preview_feature": "special_repair"}],
    )


async def test_websocket_update_preview_feature_disable(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test disabling a preview feature via WebSocket."""
    # Pre-populate storage with enabled preview feature
    hass_storage["core.labs"] = {
        "version": 1,
        "minor_version": 1,
        "key": "core.labs",
        "data": {
            "preview_feature_status": [
                {"domain": "kitchen_sink", "preview_feature": "special_repair"}
            ]
        },
    }

    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 5,
            "type": "labs/update",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": False,
        }
    )

    msg = await client.receive_json()
    assert msg["success"]

    # Verify feature is disabled
    assert not async_is_preview_feature_enabled(hass, "kitchen_sink", "special_repair")
    assert_stored_labs_data(
        hass_storage,
        [],
    )


async def test_websocket_update_nonexistent_feature(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test updating a preview feature that doesn't exist."""
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "nonexistent",
            "preview_feature": "feature",
            "enabled": True,
        }
    )
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"
    assert "not found" in msg["error"]["message"].lower()

    assert "core.labs" not in hass_storage


async def test_websocket_update_unavailable_preview_feature(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test updating a preview feature whose integration is not loaded still works."""
    # Don't load kitchen_sink integration
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Preview feature is pre-loaded, so update succeeds even though integration isn't loaded
    await client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": True,
        }
    )
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] is None

    assert_stored_labs_data(
        hass_storage,
        [{"domain": "kitchen_sink", "preview_feature": "special_repair"}],
    )


@pytest.mark.parametrize(
    "command_type",
    ["labs/list", "labs/update"],
)
async def test_websocket_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
    hass_storage: dict[str, Any],
    command_type: str,
) -> None:
    """Test that websocket commands require admin privileges."""
    # Remove admin privileges
    hass_admin_user.groups = []

    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    command = {"type": command_type}
    if command_type == "labs/update":
        command.update(
            {
                "domain": "kitchen_sink",
                "preview_feature": "special_repair",
                "enabled": True,
            }
        )

    await client.send_json_auto_id(command)
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"

    assert "core.labs" not in hass_storage


async def test_websocket_update_validates_enabled_parameter(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that enabled parameter must be boolean."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Try with string instead of boolean
    await client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": "true",
        }
    )
    msg = await client.receive_json()

    assert not msg["success"]
    # Validation error from voluptuous


async def test_storage_persists_preview_feature_across_calls(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test that storage persists preview feature state across multiple calls."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    assert "core.labs" not in hass_storage

    # Enable the preview feature
    await client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": True,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    assert_stored_labs_data(
        hass_storage,
        [{"domain": "kitchen_sink", "preview_feature": "special_repair"}],
    )

    # List preview features - should show enabled
    await client.send_json_auto_id({"type": "labs/list"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["features"][0]["enabled"] is True

    # Disable preview feature
    await client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": False,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]

    assert_stored_labs_data(
        hass_storage,
        [],
    )

    # List preview features - should show disabled
    await client.send_json_auto_id({"type": "labs/list"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["features"][0]["enabled"] is False


async def test_preview_feature_urls_present(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that preview features include feedback and report URLs."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "labs/list"})
    msg = await client.receive_json()

    assert msg["success"]
    feature = msg["result"]["features"][0]
    assert "feedback_url" in feature
    assert "learn_more_url" in feature
    assert "report_issue_url" in feature
    assert feature["feedback_url"] is not None
    assert feature["learn_more_url"] is not None
    assert feature["report_issue_url"] is not None


@pytest.mark.parametrize(
    (
        "create_backup",
        "backup_fails",
        "enabled",
        "should_call_backup",
        "should_succeed",
    ),
    [
        # Enable with successful backup
        (True, False, True, True, True),
        # Enable with failed backup
        (True, True, True, True, False),
        # Disable ignores backup flag
        (True, False, False, False, True),
    ],
    ids=[
        "enable_with_backup_success",
        "enable_with_backup_failure",
        "disable_ignores_backup",
    ],
)
async def test_websocket_update_preview_feature_backup_scenarios(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    create_backup: bool,
    backup_fails: bool,
    enabled: bool,
    should_call_backup: bool,
    should_succeed: bool,
) -> None:
    """Test various backup scenarios when updating preview features."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Mock the backup manager
    mock_backup_manager = AsyncMock()
    if backup_fails:
        mock_backup_manager.async_create_automatic_backup = AsyncMock(
            side_effect=Exception("Backup failed")
        )
    else:
        mock_backup_manager.async_create_automatic_backup = AsyncMock()

    with patch(
        "homeassistant.components.labs.websocket_api.async_get_manager",
        return_value=mock_backup_manager,
    ):
        await client.send_json_auto_id(
            {
                "type": "labs/update",
                "domain": "kitchen_sink",
                "preview_feature": "special_repair",
                "enabled": enabled,
                "create_backup": create_backup,
            }
        )
        msg = await client.receive_json()

    if should_succeed:
        assert msg["success"]
        if should_call_backup:
            mock_backup_manager.async_create_automatic_backup.assert_called_once()
        else:
            mock_backup_manager.async_create_automatic_backup.assert_not_called()
    else:
        assert not msg["success"]
        assert msg["error"]["code"] == "unknown_error"
        assert "backup" in msg["error"]["message"].lower()
        # Verify preview feature was NOT enabled
        assert not async_is_preview_feature_enabled(
            hass, "kitchen_sink", "special_repair"
        )


async def test_websocket_list_multiple_enabled_features(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test listing when multiple preview features are enabled."""
    # Pre-populate with multiple enabled features
    hass_storage["core.labs"] = {
        "version": 1,
        "data": {
            "preview_feature_status": [
                {"domain": "kitchen_sink", "preview_feature": "special_repair"},
            ]
        },
    }

    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "labs/list"})
    msg = await client.receive_json()

    assert msg["success"]
    features = msg["result"]["features"]
    assert len(features) >= 1
    # Verify at least one is enabled
    enabled_features = [f for f in features if f["enabled"]]
    assert len(enabled_features) == 1


async def test_websocket_update_rapid_toggle(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test rapid toggling of a preview feature."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Enable
    await client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": True,
        }
    )
    msg1 = await client.receive_json()
    assert msg1["success"]

    # Disable immediately
    await client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": False,
        }
    )
    msg2 = await client.receive_json()
    assert msg2["success"]

    # Enable again
    await client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": True,
        }
    )
    msg3 = await client.receive_json()
    assert msg3["success"]

    # Final state should be enabled
    assert async_is_preview_feature_enabled(hass, "kitchen_sink", "special_repair")


async def test_websocket_update_same_state_idempotent(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that enabling an already-enabled feature is idempotent."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Enable feature
    await client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": True,
        }
    )
    msg1 = await client.receive_json()
    assert msg1["success"]

    # Enable again (should be idempotent)
    await client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": True,
        }
    )
    msg2 = await client.receive_json()
    assert msg2["success"]

    # Should still be enabled
    assert async_is_preview_feature_enabled(hass, "kitchen_sink", "special_repair")


async def test_websocket_list_filtered_by_loaded_components(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that list only shows features from loaded integrations."""
    # Don't load kitchen_sink - its preview feature shouldn't appear
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "labs/list"})
    msg = await client.receive_json()

    assert msg["success"]
    # Should be empty since kitchen_sink isn't loaded
    assert msg["result"]["features"] == []

    # Now load kitchen_sink
    hass.config.components.add("kitchen_sink")

    await client.send_json_auto_id({"type": "labs/list"})
    msg = await client.receive_json()

    assert msg["success"]
    # Now should have kitchen_sink features
    assert len(msg["result"]["features"]) >= 1


async def test_websocket_update_with_missing_required_field(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that missing required fields are rejected."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Missing 'enabled' field
    await client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            # enabled is missing
        }
    )
    msg = await client.receive_json()

    assert not msg["success"]
    # Should get validation error


async def test_websocket_event_data_structure(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test that event data has correct structure."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    events = []

    def event_listener(event):
        events.append(event)

    hass.bus.async_listen(EVENT_LABS_UPDATED, event_listener)

    # Enable a feature
    await client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": True,
        }
    )
    await client.receive_json()
    await hass.async_block_till_done()

    assert len(events) == 1
    event_data = events[0].data
    # Verify all required fields are present
    assert "domain" in event_data
    assert "preview_feature" in event_data
    assert "enabled" in event_data
    assert event_data["domain"] == "kitchen_sink"
    assert event_data["preview_feature"] == "special_repair"
    assert event_data["enabled"] is True
    assert isinstance(event_data["enabled"], bool)


async def test_websocket_backup_timeout_handling(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test handling of backup timeout/long-running backup."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    # Mock backup manager with timeout
    mock_backup_manager = AsyncMock()
    mock_backup_manager.async_create_automatic_backup = AsyncMock(
        side_effect=TimeoutError("Backup timed out")
    )

    with patch(
        "homeassistant.components.labs.websocket_api.async_get_manager",
        return_value=mock_backup_manager,
    ):
        await client.send_json_auto_id(
            {
                "type": "labs/update",
                "domain": "kitchen_sink",
                "preview_feature": "special_repair",
                "enabled": True,
                "create_backup": True,
            }
        )
        msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "unknown_error"


async def test_websocket_subscribe_feature(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test subscribing to a specific preview feature."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "labs/subscribe",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
        }
    )
    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] is None

    # Initial state is sent as event
    event_msg = await client.receive_json()
    assert event_msg["type"] == "event"
    assert event_msg["event"] == {
        "preview_feature": "special_repair",
        "domain": "kitchen_sink",
        "enabled": False,
        "is_built_in": True,
        "feedback_url": ANY,
        "learn_more_url": ANY,
        "report_issue_url": ANY,
    }


async def test_websocket_subscribe_feature_receives_updates(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that subscription receives updates when feature is toggled."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "labs/subscribe",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
        }
    )
    subscribe_msg = await client.receive_json()
    assert subscribe_msg["success"]
    subscription_id = subscribe_msg["id"]

    # Initial state event
    initial_event_msg = await client.receive_json()
    assert initial_event_msg["id"] == subscription_id
    assert initial_event_msg["type"] == "event"
    assert initial_event_msg["event"]["enabled"] is False

    await client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": True,
        }
    )

    # Update event arrives before the update result
    event_msg = await client.receive_json()
    assert event_msg["id"] == subscription_id
    assert event_msg["type"] == "event"
    assert event_msg["event"] == {
        "preview_feature": "special_repair",
        "domain": "kitchen_sink",
        "enabled": True,
        "is_built_in": True,
        "feedback_url": ANY,
        "learn_more_url": ANY,
        "report_issue_url": ANY,
    }

    update_msg = await client.receive_json()
    assert update_msg["success"]


async def test_websocket_subscribe_nonexistent_feature(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test subscribing to a preview feature that doesn't exist."""
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "labs/subscribe",
            "domain": "nonexistent",
            "preview_feature": "feature",
        }
    )
    msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"
    assert "not found" in msg["error"]["message"].lower()


async def test_websocket_subscribe_does_not_require_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test that subscribe does not require admin privileges."""
    hass_admin_user.groups = []

    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "labs/subscribe",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
        }
    )
    msg = await client.receive_json()

    assert msg["success"]

    # Consume initial state event
    await client.receive_json()


async def test_websocket_subscribe_only_receives_subscribed_feature_updates(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that subscription only receives updates for the subscribed feature."""
    hass.config.components.add("kitchen_sink")
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "labs/subscribe",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
        }
    )
    subscribe_msg = await client.receive_json()
    assert subscribe_msg["success"]

    # Consume initial state event
    await client.receive_json()

    # Fire an event for a different feature
    hass.bus.async_fire(
        EVENT_LABS_UPDATED,
        {"domain": "other_domain", "preview_feature": "other_feature", "enabled": True},
    )
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "labs/update",
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": True,
        }
    )

    # Event message arrives before the update result
    # Should only receive event for subscribed feature, not the other one
    event_msg = await client.receive_json()
    assert event_msg["type"] == "event"
    assert event_msg["event"]["domain"] == "kitchen_sink"
    assert event_msg["event"]["preview_feature"] == "special_repair"

    update_msg = await client.receive_json()
    assert update_msg["success"]
