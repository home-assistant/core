"""Tests for the Lutron Caseta integration."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockBridge, async_setup_integration


@pytest.fixture
async def mock_bridge_with_mocked_set_value(hass: HomeAssistant) -> MockBridge:
    """Set up mock bridge with mocked set_value for testing open/close."""
    instance = MockBridge()

    def factory(*args: Any, **kwargs: Any) -> MockBridge:
        """Return the mock bridge instance."""
        return instance

    # Patch the methods on the instance with AsyncMocks
    instance.set_value = AsyncMock()
    instance.raise_cover = AsyncMock()
    instance.lower_cover = AsyncMock()

    await async_setup_integration(hass, factory)
    await hass.async_block_till_done()

    return instance


@pytest.fixture
async def mock_bridge_with_mocked_covers(hass: HomeAssistant) -> MockBridge:
    """Set up mock bridge with mocked cover methods for testing."""
    instance = MockBridge()

    def factory(*args: Any, **kwargs: Any) -> MockBridge:
        """Return the mock bridge instance."""
        return instance

    # Patch the methods on the instance with AsyncMocks
    instance.stop_cover = AsyncMock()
    instance.raise_cover = AsyncMock()
    instance.lower_cover = AsyncMock()

    await async_setup_integration(hass, factory)
    await hass.async_block_till_done()

    return instance


async def test_cover_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a cover unique id."""
    await async_setup_integration(hass, MockBridge)

    cover_entity_id = "cover.basement_bedroom_left_shade"

    # Assert that Caseta covers will have the bridge serial hash and the zone id as the uniqueID
    assert entity_registry.async_get(cover_entity_id).unique_id == "000004d2_802"


async def test_cover_open_close_using_set_value(
    hass: HomeAssistant, mock_bridge_with_mocked_set_value: MockBridge
) -> None:
    """Test that open/close commands use set_value to avoid stuttering."""
    mock_instance = mock_bridge_with_mocked_set_value
    cover_entity_id = "cover.basement_bedroom_left_shade"

    # Test opening the cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: cover_entity_id},
        blocking=True,
    )

    # Should use set_value(100) instead of raise_cover
    mock_instance.set_value.assert_called_with("802", 100)
    mock_instance.raise_cover.assert_not_called()

    mock_instance.set_value.reset_mock()
    mock_instance.lower_cover.reset_mock()

    # Test closing the cover
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: cover_entity_id},
        blocking=True,
    )

    # Should use set_value(0) instead of lower_cover
    mock_instance.set_value.assert_called_with("802", 0)
    mock_instance.lower_cover.assert_not_called()


async def test_cover_stop_with_direction_tracking(
    hass: HomeAssistant, mock_bridge_with_mocked_covers: MockBridge
) -> None:
    """Test that stop command sends appropriate directional command first."""
    mock_instance = mock_bridge_with_mocked_covers
    cover_entity_id = "cover.basement_bedroom_left_shade"

    # Simulate shade moving up (opening)
    mock_instance.devices["802"]["current_state"] = 30
    mock_instance.call_subscribers("802")
    await hass.async_block_till_done()

    mock_instance.devices["802"]["current_state"] = 60
    mock_instance.call_subscribers("802")
    await hass.async_block_till_done()

    # Now stop while opening
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: cover_entity_id},
        blocking=True,
    )

    # Should send raise_cover before stop_cover when opening
    mock_instance.raise_cover.assert_called_with("802")
    mock_instance.stop_cover.assert_called_with("802")
    mock_instance.lower_cover.assert_not_called()

    mock_instance.raise_cover.reset_mock()
    mock_instance.lower_cover.reset_mock()
    mock_instance.stop_cover.reset_mock()

    # Simulate shade moving down (closing)
    mock_instance.devices["802"]["current_state"] = 40
    mock_instance.call_subscribers("802")
    await hass.async_block_till_done()

    mock_instance.devices["802"]["current_state"] = 20
    mock_instance.call_subscribers("802")
    await hass.async_block_till_done()

    # Now stop while closing
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: cover_entity_id},
        blocking=True,
    )

    # Should send lower_cover before stop_cover when closing
    mock_instance.lower_cover.assert_called_with("802")
    mock_instance.stop_cover.assert_called_with("802")
    mock_instance.raise_cover.assert_not_called()


async def test_cover_stop_at_endpoints(
    hass: HomeAssistant, mock_bridge_with_mocked_covers: MockBridge
) -> None:
    """Test stop command behavior when shade is at fully open or closed."""
    mock_instance = mock_bridge_with_mocked_covers
    cover_entity_id = "cover.basement_bedroom_left_shade"

    # Test stop at fully open (100) - should infer it was opening
    mock_instance.devices["802"]["current_state"] = 100
    mock_instance.call_subscribers("802")
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: cover_entity_id},
        blocking=True,
    )

    # At fully open, should send raise_cover before stop
    mock_instance.raise_cover.assert_called_with("802")
    mock_instance.stop_cover.assert_called_with("802")

    mock_instance.raise_cover.reset_mock()
    mock_instance.lower_cover.reset_mock()
    mock_instance.stop_cover.reset_mock()

    # Test stop at fully closed (0) - should infer it was closing
    mock_instance.devices["802"]["current_state"] = 0
    mock_instance.call_subscribers("802")
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: cover_entity_id},
        blocking=True,
    )

    # At fully closed, should send lower_cover before stop
    mock_instance.lower_cover.assert_called_with("802")
    mock_instance.stop_cover.assert_called_with("802")


async def test_cover_position_heuristic_fallback(
    hass: HomeAssistant, mock_bridge_with_mocked_covers: MockBridge
) -> None:
    """Test stop command uses position heuristic when movement direction is unknown."""
    mock_instance = mock_bridge_with_mocked_covers
    cover_entity_id = "cover.basement_bedroom_left_shade"

    # Test stop at position < 50 with no movement
    # Update the device data directly in the bridge's devices dict
    mock_instance.devices["802"]["current_state"] = 30
    mock_instance.call_subscribers("802")
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: cover_entity_id},
        blocking=True,
    )

    # Position < 50, should send lower_cover
    mock_instance.lower_cover.assert_called_with("802")
    mock_instance.stop_cover.assert_called_with("802")

    mock_instance.raise_cover.reset_mock()
    mock_instance.lower_cover.reset_mock()
    mock_instance.stop_cover.reset_mock()

    # Test stop at position >= 50 with no movement
    mock_instance.devices["802"]["current_state"] = 70
    mock_instance.call_subscribers("802")
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: cover_entity_id},
        blocking=True,
    )

    # Position >= 50, should send raise_cover
    mock_instance.raise_cover.assert_called_with("802")
    mock_instance.stop_cover.assert_called_with("802")
