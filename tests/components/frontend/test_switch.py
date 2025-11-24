"""Tests for the frontend switch platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.frontend import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component


@pytest.fixture
async def setup_frontend(hass: HomeAssistant) -> None:
    """Set up the frontend integration without labs feature."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


@pytest.fixture
async def setup_frontend_with_labs(hass: HomeAssistant) -> None:
    """Set up the frontend integration with winter mode labs feature enabled."""
    with patch(
        "homeassistant.components.frontend.async_is_preview_feature_enabled",
        return_value=True,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()


async def test_winter_mode_switch_not_created_without_labs(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, setup_frontend: None
) -> None:
    """Test that the winter mode switch is not created when labs feature is disabled."""
    entity_id = "switch.winter_mode"

    # Entity should not exist when labs feature is disabled
    entry = entity_registry.async_get(entity_id)
    assert entry is None


async def test_winter_mode_switch_created_with_labs(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_frontend_with_labs: None,
) -> None:
    """Test that the winter mode switch entity is created when labs feature is enabled."""
    entity_id = "switch.winter_mode"

    # Entity should be registered when labs feature is enabled
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "frontend_winter_mode"
    assert entry.platform == "frontend"
    assert entry.translation_key == "winter_mode"


async def test_winter_mode_switch_entity_category(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    setup_frontend_with_labs: None,
) -> None:
    """Test that winter mode switch has correct entity category."""
    entity_id = "switch.winter_mode"

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.entity_category == "config"
