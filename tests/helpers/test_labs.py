"""Tests for the Home Assistant Labs helper."""

from __future__ import annotations

from typing import Any

import pytest

from homeassistant.components.labs import DOMAIN as LABS_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.labs import (
    EVENT_LABS_UPDATED,
    async_is_preview_feature_enabled,
    async_listen,
)
from homeassistant.setup import async_setup_component


async def test_async_is_preview_feature_enabled_not_setup(hass: HomeAssistant) -> None:
    """Test checking if preview feature is enabled before setup returns False."""
    # Don't set up labs integration
    result = async_is_preview_feature_enabled(hass, "kitchen_sink", "special_repair")
    assert result is False


async def test_async_is_preview_feature_enabled_nonexistent(
    hass: HomeAssistant,
) -> None:
    """Test checking if non-existent preview feature is enabled."""
    assert await async_setup_component(hass, LABS_DOMAIN, {})
    await hass.async_block_till_done()

    result = async_is_preview_feature_enabled(
        hass, "kitchen_sink", "nonexistent_feature"
    )
    assert result is False


async def test_async_is_preview_feature_enabled_when_enabled(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test checking if preview feature is enabled."""
    # Load kitchen_sink integration so preview feature exists
    hass.config.components.add("kitchen_sink")

    # Enable a preview feature via storage
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

    assert await async_setup_component(hass, LABS_DOMAIN, {})
    await hass.async_block_till_done()

    result = async_is_preview_feature_enabled(hass, "kitchen_sink", "special_repair")
    assert result is True


async def test_async_is_preview_feature_enabled_when_disabled(
    hass: HomeAssistant,
) -> None:
    """Test checking if preview feature is disabled (not in storage)."""
    # Load kitchen_sink integration so preview feature exists
    hass.config.components.add("kitchen_sink")

    assert await async_setup_component(hass, LABS_DOMAIN, {})
    await hass.async_block_till_done()

    result = async_is_preview_feature_enabled(hass, "kitchen_sink", "special_repair")
    assert result is False


@pytest.mark.parametrize(
    ("domain", "preview_feature", "expected"),
    [
        ("kitchen_sink", "special_repair", True),
        ("other", "nonexistent", False),
        ("kitchen_sink", "nonexistent", False),
    ],
)
async def test_async_is_preview_feature_enabled(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    domain: str,
    preview_feature: str,
    expected: bool,
) -> None:
    """Test async_is_preview_feature_enabled."""
    # Enable the kitchen_sink.special_repair preview feature via storage
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

    await async_setup_component(hass, LABS_DOMAIN, {})
    await hass.async_block_till_done()

    result = async_is_preview_feature_enabled(hass, domain, preview_feature)
    assert result is expected


async def test_async_listen_helper(hass: HomeAssistant) -> None:
    """Test the async_listen helper function for preview feature events."""
    # Load kitchen_sink integration
    hass.config.components.add("kitchen_sink")

    assert await async_setup_component(hass, LABS_DOMAIN, {})
    await hass.async_block_till_done()

    # Track listener calls
    listener_calls = []

    def test_listener() -> None:
        """Test listener callback."""
        listener_calls.append("called")

    # Subscribe to a specific preview feature
    unsub = async_listen(
        hass,
        domain="kitchen_sink",
        preview_feature="special_repair",
        listener=test_listener,
    )

    # Fire event for the subscribed feature
    hass.bus.async_fire(
        EVENT_LABS_UPDATED,
        {
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": True,
        },
    )
    await hass.async_block_till_done()

    # Verify listener was called
    assert len(listener_calls) == 1

    # Fire event for a different feature - should not trigger listener
    hass.bus.async_fire(
        EVENT_LABS_UPDATED,
        {
            "domain": "kitchen_sink",
            "preview_feature": "other_feature",
            "enabled": True,
        },
    )
    await hass.async_block_till_done()

    # Verify listener was not called again
    assert len(listener_calls) == 1

    # Fire event for a different domain - should not trigger listener
    hass.bus.async_fire(
        EVENT_LABS_UPDATED,
        {
            "domain": "other_domain",
            "preview_feature": "special_repair",
            "enabled": True,
        },
    )
    await hass.async_block_till_done()

    # Verify listener was not called again
    assert len(listener_calls) == 1

    # Test unsubscribe
    unsub()

    # Fire event again - should not trigger listener after unsubscribe
    hass.bus.async_fire(
        EVENT_LABS_UPDATED,
        {
            "domain": "kitchen_sink",
            "preview_feature": "special_repair",
            "enabled": True,
        },
    )
    await hass.async_block_till_done()

    # Verify listener was not called after unsubscribe
    assert len(listener_calls) == 1
