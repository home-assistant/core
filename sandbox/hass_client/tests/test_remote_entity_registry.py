"""Tests for the remote entity registry manager."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from hass_client.remotes.helpers.entity_registry import RemoteEntityRegistryManager
from hass_client.runtime import RemoteHomeAssistant
from homeassistant.helpers import entity_registry as er


def _entry_payload(entity_id: str, *, name: str) -> dict[str, object]:
    """Build a websocket entity registry payload."""
    return {
        "aliases": [f"{name} alias"],
        "area_id": None,
        "categories": {},
        "capabilities": None,
        "config_entry_id": None,
        "config_subentry_id": None,
        "created_at": 1_700_000_000.0,
        "device_class": None,
        "device_id": None,
        "disabled_by": None,
        "entity_category": None,
        "entity_id": entity_id,
        "has_entity_name": True,
        "hidden_by": None,
        "icon": None,
        "id": f"{entity_id}-id",
        "labels": ["test"],
        "modified_at": 1_700_000_001.0,
        "name": name,
        "options": {},
        "original_device_class": None,
        "original_icon": None,
        "original_name": name,
        "platform": "demo",
        "translation_key": None,
        "unique_id": f"{entity_id}-unique",
    }


def test_remote_entity_registry_manager_refreshes_snapshot(tmp_path: Path) -> None:
    """Load the remote entity registry snapshot into the local registry."""

    async def run_test() -> None:
        remote_api = AsyncMock()
        remote_api.async_get_entity_registry.return_value = [
            {"entity_id": "light.kitchen"}
        ]
        remote_api.async_get_entity_registry_entry.return_value = _entry_payload(
            "light.kitchen",
            name="Kitchen",
        )

        hass = RemoteHomeAssistant(str(tmp_path))
        hass.remote_api = remote_api
        manager = RemoteEntityRegistryManager(hass)

        await manager.async_refresh()

        entry = er.async_get(hass).entities["light.kitchen"]
        assert entry.entity_id == "light.kitchen"
        assert entry.aliases == ["Kitchen alias"]
        assert entry.labels == {"test"}

    asyncio.run(run_test())


def test_remote_entity_registry_manager_handles_renames(tmp_path: Path) -> None:
    """Replace the old entity id when the remote registry renames an entry."""

    async def run_test() -> None:
        remote_api = AsyncMock()
        old_payload = _entry_payload("light.old_name", name="Old")
        new_payload = _entry_payload("light.new_name", name="New")
        remote_api.async_get_entity_registry.return_value = [
            {"entity_id": "light.old_name"}
        ]
        remote_api.async_get_entity_registry_entry.side_effect = [
            old_payload,
            new_payload,
        ]

        hass = RemoteHomeAssistant(str(tmp_path))
        hass.remote_api = remote_api
        manager = RemoteEntityRegistryManager(hass)

        await manager.async_refresh()
        await manager._handle_event(
            {
                "event": {
                    "context": None,
                    "data": {
                        "action": "update",
                        "entity_id": "light.new_name",
                        "old_entity_id": "light.old_name",
                    },
                    "time_fired": 1_700_000_002.0,
                }
            }
        )

        entities = er.async_get(hass).entities
        assert "light.old_name" not in entities
        assert entities["light.new_name"].name == "New"

    asyncio.run(run_test())
