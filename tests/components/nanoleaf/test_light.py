"""Tests for the Nanoleaf light platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
)
from homeassistant.components.nanoleaf.light import NanoleafLight


@pytest.fixture
def mock_nanoleaf():
    """Create a mock Nanoleaf object."""
    nanoleaf = MagicMock()
    nanoleaf.serial_no = "ABCDEF123456"
    nanoleaf.color_temperature_max = 4500
    nanoleaf.color_temperature_min = 1200
    nanoleaf.is_on = False
    nanoleaf.brightness = 50
    nanoleaf.color_temperature = 2700
    nanoleaf.hue = 120
    nanoleaf.saturation = 50
    nanoleaf.color_mode = "hs"
    nanoleaf.effect = "Rainbow"
    nanoleaf.effects_list = ["Rainbow", "Sunset", "Nemo"]
    nanoleaf.turn_on = AsyncMock()
    nanoleaf.turn_off = AsyncMock()
    nanoleaf.set_brightness = AsyncMock()
    nanoleaf.set_effect = AsyncMock()
    nanoleaf.set_hue = AsyncMock()
    nanoleaf.set_saturation = AsyncMock()
    nanoleaf.set_color_temperature = AsyncMock()
    return nanoleaf


@pytest.fixture
def mock_coordinator(mock_nanoleaf):
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.nanoleaf = mock_nanoleaf
    return coordinator


async def test_async_turn_on_writes_state(mock_coordinator):
    """Test that async_turn_on calls async_write_ha_state."""
    entity = NanoleafLight(mock_coordinator)

    with patch.object(entity, "async_write_ha_state") as mock_async_write_ha_state:
        await entity.async_turn_on()
        mock_async_write_ha_state.assert_called_once()


async def test_async_turn_off_writes_state(mock_coordinator):
    """Test that async_turn_off calls async_write_ha_state."""
    entity = NanoleafLight(mock_coordinator)

    with patch.object(entity, "async_write_ha_state") as mock_async_write_ha_state:
        await entity.async_turn_off()
        mock_async_write_ha_state.assert_called_once()


async def test_async_turn_on_with_options_writes_state(mock_coordinator):
    """Test that async_turn_on with various options calls async_write_ha_state."""
    entity = NanoleafLight(mock_coordinator)

    test_cases = [
        {ATTR_BRIGHTNESS: 128},
        {ATTR_HS_COLOR: (180, 75)},
        {ATTR_COLOR_TEMP_KELVIN: 3000},
        {ATTR_EFFECT: "Rainbow"},
        {ATTR_TRANSITION: 2},
        {ATTR_BRIGHTNESS: 128, ATTR_TRANSITION: 2},
    ]

    for options in test_cases:
        with patch.object(entity, "async_write_ha_state") as mock_async_write_ha_state:
            await entity.async_turn_on(**options)
            mock_async_write_ha_state.assert_called_once()


async def test_async_turn_off_with_transition_writes_state(mock_coordinator):
    """Test that async_turn_off with transition calls async_write_ha_state."""
    entity = NanoleafLight(mock_coordinator)

    with patch.object(entity, "async_write_ha_state") as mock_async_write_ha_state:
        await entity.async_turn_off(**{ATTR_TRANSITION: 5})
        mock_async_write_ha_state.assert_called_once()


async def test_effect_validation(mock_coordinator):
    """Test that invalid effects raise ValueError."""
    mock_coordinator.nanoleaf.effects_list = ["Rainbow", "Sunset"]
    entity = NanoleafLight(mock_coordinator)

    with patch.object(entity, "async_write_ha_state") as mock_async_write_ha_state:
        with pytest.raises(ValueError):
            await entity.async_turn_on(**{ATTR_EFFECT: "Invalid Effect"})
        mock_async_write_ha_state.assert_not_called()
