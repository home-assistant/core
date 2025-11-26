"""Tests for the Home Assistant Labs integration setup."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.labs import (
    EVENT_LABS_UPDATED,
    async_is_preview_feature_enabled,
    async_listen,
)
from homeassistant.components.labs.const import DOMAIN, LABS_DATA
from homeassistant.components.labs.models import LabPreviewFeature
from homeassistant.core import HomeAssistant
from homeassistant.loader import Integration
from homeassistant.setup import async_setup_component

from . import assert_stored_labs_data


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test the Labs integration setup."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Verify WebSocket commands are registered
    assert "labs/list" in hass.data["websocket_api"]
    assert "labs/update" in hass.data["websocket_api"]


async def test_async_is_preview_feature_enabled_not_setup(hass: HomeAssistant) -> None:
    """Test checking if preview feature is enabled before setup returns False."""
    # Don't set up labs integration
    result = async_is_preview_feature_enabled(hass, "kitchen_sink", "special_repair")
    assert result is False


async def test_async_is_preview_feature_enabled_nonexistent(
    hass: HomeAssistant,
) -> None:
    """Test checking if non-existent preview feature is enabled."""
    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    result = async_is_preview_feature_enabled(hass, "kitchen_sink", "special_repair")
    assert result is True


async def test_async_is_preview_feature_enabled_when_disabled(
    hass: HomeAssistant,
) -> None:
    """Test checking if preview feature is disabled (not in storage)."""
    # Load kitchen_sink integration so preview feature exists
    hass.config.components.add("kitchen_sink")

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    result = async_is_preview_feature_enabled(hass, "kitchen_sink", "special_repair")
    assert result is False


@pytest.mark.parametrize(
    (
        "features_to_store",
        "expected_enabled",
        "expected_cleaned",
        "expected_cleaned_store",
    ),
    [
        # Single stale feature cleanup
        (
            [
                {"domain": "kitchen_sink", "preview_feature": "special_repair"},
                {"domain": "nonexistent_domain", "preview_feature": "fake_feature"},
            ],
            [("kitchen_sink", "special_repair")],
            [("nonexistent_domain", "fake_feature")],
            [{"domain": "kitchen_sink", "preview_feature": "special_repair"}],
        ),
        # Multiple stale features cleanup
        (
            [
                {"domain": "kitchen_sink", "preview_feature": "special_repair"},
                {"domain": "stale_domain_1", "preview_feature": "old_feature"},
                {"domain": "stale_domain_2", "preview_feature": "another_old"},
                {"domain": "stale_domain_3", "preview_feature": "yet_another"},
            ],
            [("kitchen_sink", "special_repair")],
            [
                ("stale_domain_1", "old_feature"),
                ("stale_domain_2", "another_old"),
                ("stale_domain_3", "yet_another"),
            ],
            [{"domain": "kitchen_sink", "preview_feature": "special_repair"}],
        ),
        # All features cleaned (no integrations loaded)
        (
            [{"domain": "nonexistent", "preview_feature": "fake"}],
            [],
            [("nonexistent", "fake")],
            [],
        ),
    ],
)
async def test_storage_cleanup_stale_features(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    features_to_store: list[dict[str, str]],
    expected_enabled: list[tuple[str, str]],
    expected_cleaned: list[tuple[str, str]],
    expected_cleaned_store: list[dict[str, str]],
) -> None:
    """Test that stale preview features are removed from storage on setup."""
    # Load kitchen_sink only if we expect any features to remain
    if expected_enabled:
        hass.config.components.add("kitchen_sink")

    hass_storage["core.labs"] = {
        "version": 1,
        "minor_version": 1,
        "key": "core.labs",
        "data": {"preview_feature_status": features_to_store},
    }

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Verify expected features are preserved
    for domain, feature in expected_enabled:
        assert async_is_preview_feature_enabled(hass, domain, feature)

    # Verify stale features were cleaned up
    for domain, feature in expected_cleaned:
        assert not async_is_preview_feature_enabled(hass, domain, feature)

    assert_stored_labs_data(hass_storage, expected_cleaned_store)


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

    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    result = async_is_preview_feature_enabled(hass, domain, preview_feature)
    assert result is expected


async def test_preview_feature_full_key(hass: HomeAssistant) -> None:
    """Test that preview feature full_key property returns correct format."""
    feature = LabPreviewFeature(
        domain="test_domain",
        preview_feature="test_feature",
        feedback_url="https://feedback.example.com",
    )

    assert feature.full_key == "test_domain.test_feature"


async def test_preview_feature_to_dict_with_all_urls(hass: HomeAssistant) -> None:
    """Test LabPreviewFeature.to_dict with all URLs populated."""
    feature = LabPreviewFeature(
        domain="test_domain",
        preview_feature="test_feature",
        feedback_url="https://feedback.example.com",
        learn_more_url="https://learn.example.com",
        report_issue_url="https://issue.example.com",
    )

    result = feature.to_dict(enabled=True)

    assert result == {
        "preview_feature": "test_feature",
        "domain": "test_domain",
        "enabled": True,
        "is_built_in": True,
        "feedback_url": "https://feedback.example.com",
        "learn_more_url": "https://learn.example.com",
        "report_issue_url": "https://issue.example.com",
    }


async def test_preview_feature_to_dict_with_no_urls(hass: HomeAssistant) -> None:
    """Test LabPreviewFeature.to_dict with no URLs (all None)."""
    feature = LabPreviewFeature(
        domain="test_domain",
        preview_feature="test_feature",
    )

    result = feature.to_dict(enabled=False)

    assert result == {
        "preview_feature": "test_feature",
        "domain": "test_domain",
        "enabled": False,
        "is_built_in": True,
        "feedback_url": None,
        "learn_more_url": None,
        "report_issue_url": None,
    }


async def test_custom_integration_with_preview_features(
    hass: HomeAssistant,
) -> None:
    """Test that custom integrations with preview features are loaded."""
    # Create a mock custom integration with preview features
    mock_integration = Mock(spec=Integration)
    mock_integration.domain = "custom_test"
    mock_integration.preview_features = {
        "test_feature": {
            "feedback_url": "https://feedback.test",
            "learn_more_url": "https://learn.test",
        }
    }

    with patch(
        "homeassistant.components.labs.async_get_custom_components",
        return_value={"custom_test": mock_integration},
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    # Verify the custom integration's preview feature can be checked
    # (This confirms it was loaded properly)
    assert not async_is_preview_feature_enabled(hass, "custom_test", "test_feature")


@pytest.mark.parametrize(
    ("is_custom", "expected_is_built_in"),
    [
        (False, True),  # Built-in integration
        (True, False),  # Custom integration
    ],
)
async def test_preview_feature_is_built_in_flag(
    hass: HomeAssistant,
    is_custom: bool,
    expected_is_built_in: bool,
) -> None:
    """Test that preview features have correct is_built_in flag."""
    if is_custom:
        # Create a mock custom integration
        mock_integration = Mock(spec=Integration)
        mock_integration.domain = "custom_test"
        mock_integration.preview_features = {
            "custom_feature": {"feedback_url": "https://feedback.test"}
        }
        with patch(
            "homeassistant.components.labs.async_get_custom_components",
            return_value={"custom_test": mock_integration},
        ):
            assert await async_setup_component(hass, DOMAIN, {})
            await hass.async_block_till_done()
        feature_key = "custom_test.custom_feature"
    else:
        # Load built-in kitchen_sink integration
        hass.config.components.add("kitchen_sink")
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        feature_key = "kitchen_sink.special_repair"

    labs_data = hass.data[LABS_DATA]
    assert feature_key in labs_data.preview_features
    feature = labs_data.preview_features[feature_key]
    assert feature.is_built_in is expected_is_built_in


@pytest.mark.parametrize(
    ("is_built_in", "expected_default"),
    [
        (True, True),
        (False, False),
        (None, True),  # Default value when not specified
    ],
)
async def test_preview_feature_to_dict_is_built_in(
    hass: HomeAssistant,
    is_built_in: bool | None,
    expected_default: bool,
) -> None:
    """Test that to_dict correctly handles is_built_in field."""
    if is_built_in is None:
        # Test default value
        feature = LabPreviewFeature(
            domain="test_domain",
            preview_feature="test_feature",
        )
    else:
        feature = LabPreviewFeature(
            domain="test_domain",
            preview_feature="test_feature",
            is_built_in=is_built_in,
        )

    assert feature.is_built_in is expected_default
    result = feature.to_dict(enabled=True)
    assert result["is_built_in"] is expected_default


async def test_async_listen_helper(hass: HomeAssistant) -> None:
    """Test the async_listen helper function for preview feature events."""
    # Load kitchen_sink integration
    hass.config.components.add("kitchen_sink")

    assert await async_setup_component(hass, DOMAIN, {})
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
