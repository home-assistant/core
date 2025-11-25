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
