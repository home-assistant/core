"""Tests for Entity Migration WebSocket API."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components.entity_migration.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


async def test_websocket_scan_success(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: None,
    mock_all_helpers: dict[str, MagicMock],
) -> None:
    """Test WebSocket scan command returns results."""
    hass.states.async_set("sensor.test_entity", "on")

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "entity_migration/scan",
            "entity_id": "sensor.test_entity",
        }
    )

    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["source_entity_id"] == "sensor.test_entity"
    assert "references" in response["result"]
    assert "total_count" in response["result"]


async def test_websocket_scan_with_references(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: None,
    mock_all_helpers: dict[str, MagicMock],
) -> None:
    """Test WebSocket scan returns found references."""
    hass.states.async_set("sensor.temperature", "21")
    hass.states.async_set(
        "automation.climate_control",
        "on",
        {"friendly_name": "Climate Control"},
    )

    mock_all_helpers["automations"].return_value = ["automation.climate_control"]

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "entity_migration/scan",
            "entity_id": "sensor.temperature",
        }
    )

    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["total_count"] == 1
    assert "automation" in response["result"]["references"]


async def test_websocket_scan_invalid_entity_id(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: None,
) -> None:
    """Test WebSocket scan with invalid entity ID format."""
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "entity_migration/scan",
            "entity_id": "invalid_format",
        }
    )

    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_entity_id"


async def test_websocket_scan_missing_entity_id(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: None,
) -> None:
    """Test WebSocket scan without entity_id parameter."""
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "entity_migration/scan",
        }
    )

    response = await client.receive_json()
    assert not response["success"]


async def test_websocket_scan_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: None,
    hass_read_only_access_token: str,
) -> None:
    """Test WebSocket scan requires admin access."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json(
        {
            "id": 1,
            "type": "entity_migration/scan",
            "entity_id": "sensor.test",
        }
    )

    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"


async def test_websocket_scan_empty_references(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: None,
    mock_all_helpers: dict[str, MagicMock],
) -> None:
    """Test WebSocket scan with no references found."""
    hass.states.async_set("sensor.unused_entity", "on")

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "entity_migration/scan",
            "entity_id": "sensor.unused_entity",
        }
    )

    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["total_count"] == 0
    assert response["result"]["references"] == {}


async def test_websocket_validate_success(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: None,
    entity_registry,
) -> None:
    """Test WebSocket validate command returns compatibility result."""
    # Register both entities
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
    )
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "target_id",
        suggested_object_id="target",
    )

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "entity_migration/validate",
            "source_entity_id": "sensor.source",
            "target_entity_id": "sensor.target",
        }
    )

    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["valid"] is True
    assert response["result"]["source_entity_id"] == "sensor.source"
    assert response["result"]["target_entity_id"] == "sensor.target"
    assert "warnings" in response["result"]
    assert "blocking_errors" in response["result"]


async def test_websocket_validate_target_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: None,
    entity_registry,
) -> None:
    """Test WebSocket validate when target doesn't exist."""
    # Only register source entity
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
    )

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "entity_migration/validate",
            "source_entity_id": "sensor.source",
            "target_entity_id": "sensor.nonexistent",
        }
    )

    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["valid"] is False
    assert len(response["result"]["blocking_errors"]) >= 1


async def test_websocket_validate_domain_mismatch(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: None,
    entity_registry,
) -> None:
    """Test WebSocket validate returns warning for domain mismatch."""
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
    )
    entity_registry.async_get_or_create(
        "binary_sensor",
        "test",
        "target_id",
        suggested_object_id="target",
    )

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "entity_migration/validate",
            "source_entity_id": "sensor.source",
            "target_entity_id": "binary_sensor.target",
        }
    )

    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["valid"] is True  # Domain mismatch is warning, not error
    assert len(response["result"]["warnings"]) >= 1


async def test_websocket_validate_invalid_entity_id(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: None,
) -> None:
    """Test WebSocket validate with invalid entity ID format."""
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "entity_migration/validate",
            "source_entity_id": "invalid_format",
            "target_entity_id": "sensor.target",
        }
    )

    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_entity_id"


async def test_websocket_migrate_success(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: None,
    mock_all_helpers: dict[str, MagicMock],
    entity_registry,
) -> None:
    """Test WebSocket migrate command."""
    # Register both entities
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
    )
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "target_id",
        suggested_object_id="target",
    )
    hass.states.async_set("sensor.source", "on")

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "entity_migration/migrate",
            "source_entity_id": "sensor.source",
            "target_entity_id": "sensor.target",
            "dry_run": True,
        }
    )

    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["success"] is True
    assert response["result"]["source_entity_id"] == "sensor.source"
    assert response["result"]["target_entity_id"] == "sensor.target"
    assert response["result"]["dry_run"] is True


async def test_websocket_migrate_blocked_by_validation(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: None,
    entity_registry,
) -> None:
    """Test WebSocket migrate is blocked when target doesn't exist."""
    # Only register source entity
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
    )

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "entity_migration/migrate",
            "source_entity_id": "sensor.source",
            "target_entity_id": "sensor.nonexistent",
        }
    )

    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "validation_failed"


async def test_websocket_migrate_force_bypasses_validation(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: None,
    mock_all_helpers: dict[str, MagicMock],
    entity_registry,
) -> None:
    """Test WebSocket migrate with force=true bypasses validation."""
    # Only register source entity (target doesn't exist)
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source_id",
        suggested_object_id="source",
    )
    hass.states.async_set("sensor.source", "on")

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "entity_migration/migrate",
            "source_entity_id": "sensor.source",
            "target_entity_id": "sensor.nonexistent",
            "force": True,
            "dry_run": True,
        }
    )

    response = await client.receive_json()
    # Should succeed because force bypasses validation
    assert response["success"]
    assert response["result"]["success"] is True


async def test_websocket_migrate_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: None,
    hass_read_only_access_token: str,
) -> None:
    """Test WebSocket migrate requires admin access."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json(
        {
            "id": 1,
            "type": "entity_migration/migrate",
            "source_entity_id": "sensor.source",
            "target_entity_id": "sensor.target",
        }
    )

    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"


async def test_websocket_validate_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    init_integration: None,
    hass_read_only_access_token: str,
) -> None:
    """Test WebSocket validate requires admin access."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    await client.send_json(
        {
            "id": 1,
            "type": "entity_migration/validate",
            "source_entity_id": "sensor.source",
            "target_entity_id": "sensor.target",
        }
    )

    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "unauthorized"
