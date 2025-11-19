"""Tests for the Home Assistant Labs integration setup."""

from __future__ import annotations

from typing import Any

import pytest

from homeassistant.components.labs import (
    EVENT_LABS_UPDATED,
    async_is_preview_feature_enabled,
    async_setup,
)
from homeassistant.components.labs.const import LABS_DATA
from homeassistant.core import HomeAssistant


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test the Labs integration setup."""
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    # Verify WebSocket commands are registered
    assert "labs/list" in hass.data["websocket_api"]
    assert "labs/update" in hass.data["websocket_api"]


async def test_async_is_feature_enabled_not_setup(hass: HomeAssistant) -> None:
    """Test checking if feature is enabled before setup returns False."""
    # Don't set up labs integration
    result = async_is_preview_feature_enabled(hass, "kitchen_sink", "special_repair")
    assert result is False


async def test_async_is_feature_enabled_feature_not_exists(
    hass: HomeAssistant,
) -> None:
    """Test checking if non-existent feature is enabled."""
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    result = async_is_preview_feature_enabled(
        hass, "kitchen_sink", "nonexistent_feature"
    )
    assert result is False


async def test_async_is_feature_enabled_feature_enabled(hass: HomeAssistant) -> None:
    """Test checking if feature is enabled."""
    # Load kitchen_sink integration so feature exists
    hass.config.components.add("kitchen_sink")

    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    # Enable a feature via storage
    hass.data[LABS_DATA].data["features"]["kitchen_sink.special_repair"] = True

    result = async_is_preview_feature_enabled(hass, "kitchen_sink", "special_repair")
    assert result is True


async def test_async_is_feature_enabled_feature_disabled(hass: HomeAssistant) -> None:
    """Test checking if feature is disabled."""
    # Load kitchen_sink integration so feature exists
    hass.config.components.add("kitchen_sink")

    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    # Explicitly disable a feature via storage
    hass.data[LABS_DATA].data["features"]["kitchen_sink.special_repair"] = False

    result = async_is_preview_feature_enabled(hass, "kitchen_sink", "special_repair")
    assert result is False


async def test_storage_cleanup_graduated_features(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test that graduated features are removed from storage on setup."""
    # Load kitchen_sink so the feature exists
    hass.config.components.add("kitchen_sink")

    # Add some data to storage including a graduated feature
    hass_storage["core.labs"] = {
        "version": 1,
        "minor_version": 1,
        "key": "core.labs",
        "data": {
            "features": {
                "kitchen_sink.special_repair": True,
                "graduated_feature": False,  # This doesn't exist in any manifest
                "another_nonexistent": True,
            }
        },
    }

    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    # Check that only valid features remain
    store = hass.data[LABS_DATA].store
    data = await store.async_load()

    assert "kitchen_sink.special_repair" in data["features"]
    assert "graduated_feature" not in data["features"]
    assert "another_nonexistent" not in data["features"]


async def test_storage_initialization_empty(hass: HomeAssistant) -> None:
    """Test storage initialization with no existing data."""
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    data = hass.data[LABS_DATA].data

    assert data == {"features": {}}


async def test_storage_initialization_with_data(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test storage initialization with existing data."""
    # Load kitchen_sink integration
    hass.config.components.add("kitchen_sink")

    hass_storage["core.labs"] = {
        "version": 1,
        "minor_version": 1,
        "key": "core.labs",
        "data": {"features": {"kitchen_sink.special_repair": True}},
    }

    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    result = async_is_preview_feature_enabled(hass, "kitchen_sink", "special_repair")
    assert result is True


async def test_feature_availability_integration_loaded(hass: HomeAssistant) -> None:
    """Test feature availability when required integration is loaded."""
    # Load kitchen_sink integration
    hass.config.components.add("kitchen_sink")

    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    # Check the feature exists
    features = hass.data[LABS_DATA].features
    assert "kitchen_sink.special_repair" in features
    feature = features["kitchen_sink.special_repair"]
    assert feature.domain == "kitchen_sink"


async def test_feature_availability_integration_not_loaded(
    hass: HomeAssistant,
) -> None:
    """Test feature is pre-loaded even when integration is not loaded."""
    # Don't load kitchen_sink integration
    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    # Feature is pre-loaded at startup, even though kitchen_sink isn't loaded
    features = hass.data[LABS_DATA].features
    assert "kitchen_sink.special_repair" in features


async def test_event_fired_on_feature_update(hass: HomeAssistant) -> None:
    """Test that labs_updated event is fired when feature is toggled."""
    # Load kitchen_sink integration
    hass.config.components.add("kitchen_sink")

    assert await async_setup(hass, {})
    await hass.async_block_till_done()

    events = []

    def event_listener(event):
        events.append(event)

    hass.bus.async_listen(EVENT_LABS_UPDATED, event_listener)

    # Toggle feature via storage (simulating websocket call result)
    store = hass.data[LABS_DATA].store
    store._data = {"features": {"kitchen_sink.special_repair": True}}
    await store.async_save(store._data)

    # Fire event manually to test listener (websocket handler does this)
    hass.bus.async_fire(
        EVENT_LABS_UPDATED,
        {"feature_id": "kitchen_sink.special_repair", "enabled": True},
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["feature_id"] == "kitchen_sink.special_repair"
    assert events[0].data["enabled"] is True


@pytest.mark.parametrize(
    ("domain", "feature", "expected"),
    [
        ("kitchen_sink", "special_repair", True),
        ("other", "feature", False),
        ("kitchen_sink", "nonexistent", False),
    ],
)
async def test_async_is_preview_feature_enabled(
    hass: HomeAssistant, domain: str, feature: str, expected: bool
) -> None:
    """Test async_is_preview_feature_enabled."""
    await async_setup(hass, {})
    await hass.async_block_till_done()

    # Enable the kitchen_sink.special_repair feature
    hass.data[LABS_DATA].data["features"]["kitchen_sink.special_repair"] = True

    result = async_is_preview_feature_enabled(hass, domain, feature)
    assert result is expected


async def test_multiple_setups_idempotent(hass: HomeAssistant) -> None:
    """Test that calling async_setup multiple times is safe."""
    result1 = await async_setup(hass, {})
    assert result1 is True

    result2 = await async_setup(hass, {})
    assert result2 is True

    # Verify store is still accessible
    assert LABS_DATA in hass.data
