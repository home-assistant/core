"""Tests for the HomeKit input visibility storage."""

from typing import Any

import pytest

from homeassistant.components.homekit.const import DOMAIN
from homeassistant.components.homekit.util import (
    get_visibility_storage_filename_for_entry_id,
)
from homeassistant.components.homekit.visibility import AccessoryVisibilityStorage
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("visibility_storage")
async def test_visibility_persist_and_restore(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Hidden sources persist to storage and restore in a fresh instance."""
    entry = MockConfigEntry(domain=DOMAIN)

    storage = AccessoryVisibilityStorage(hass, entry.entry_id)
    await storage.async_initialize()
    assert storage.get_hidden_sources("media_player.tv") == []

    storage.async_set_hidden_sources("media_player.tv", {"HDMI 3", "HDMI 1"})
    await storage.async_save()

    restored = AccessoryVisibilityStorage(hass, entry.entry_id)
    await restored.async_initialize()
    assert restored.get_hidden_sources("media_player.tv") == ["HDMI 1", "HDMI 3"]


@pytest.mark.usefixtures("visibility_storage")
async def test_visibility_clearing_removes_entity(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Setting an empty source set drops the entity from storage."""
    entry = MockConfigEntry(domain=DOMAIN)

    storage = AccessoryVisibilityStorage(hass, entry.entry_id)
    await storage.async_initialize()
    storage.async_set_hidden_sources("media_player.tv", {"HDMI 1"})
    storage.async_set_hidden_sources("media_player.tv", set())
    await storage.async_save()

    restored = AccessoryVisibilityStorage(hass, entry.entry_id)
    await restored.async_initialize()
    assert restored.get_hidden_sources("media_player.tv") == []


@pytest.mark.usefixtures("visibility_storage")
async def test_visibility_storage_filename(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Visibility storage uses the expected filename."""
    entry = MockConfigEntry(domain=DOMAIN)

    storage = AccessoryVisibilityStorage(hass, entry.entry_id)
    await storage.async_initialize()
    assert storage.store is not None
    assert storage.store.path.endswith(
        get_visibility_storage_filename_for_entry_id(entry.entry_id)
    )
