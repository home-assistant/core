"""Test Evil Genius Labs light."""
from unittest.mock import patch

import pytest

from homeassistant.components.light import (
    ATTR_COLOR_MODE,
    ATTR_SUPPORTED_COLOR_MODES,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES


@pytest.mark.parametrize("platforms", [("light",)])
async def test_works(hass, setup_evil_genius_labs):
    """Test it works."""
    state = hass.states.get("light.fibonacci256_23d4")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["brightness"] == 128
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.RGB
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.RGB]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == LightEntityFeature.EFFECT


@pytest.mark.parametrize("platforms", [("light",)])
async def test_turn_on_color(hass, setup_evil_genius_labs):
    """Test turning on with a color."""
    with patch(
        "pyevilgenius.EvilGeniusDevice.set_path_value"
    ) as mock_set_path_value, patch(
        "pyevilgenius.EvilGeniusDevice.set_rgb_color"
    ) as mock_set_rgb_color:
        await hass.services.async_call(
            "light",
            "turn_on",
            {
                "entity_id": "light.fibonacci256_23d4",
                "brightness": 100,
                "rgb_color": (10, 20, 30),
            },
            blocking=True,
        )

    assert len(mock_set_path_value.mock_calls) == 2
    mock_set_path_value.mock_calls[0][1] == ("brightness", 100)
    mock_set_path_value.mock_calls[1][1] == ("power", 1)

    assert len(mock_set_rgb_color.mock_calls) == 1
    mock_set_rgb_color.mock_calls[0][1] == (10, 20, 30)


@pytest.mark.parametrize("platforms", [("light",)])
async def test_turn_on_effect(hass, setup_evil_genius_labs):
    """Test turning on with an effect."""
    with patch("pyevilgenius.EvilGeniusDevice.set_path_value") as mock_set_path_value:
        await hass.services.async_call(
            "light",
            "turn_on",
            {
                "entity_id": "light.fibonacci256_23d4",
                "effect": "Pride Playground",
            },
            blocking=True,
        )

    assert len(mock_set_path_value.mock_calls) == 2
    mock_set_path_value.mock_calls[0][1] == ("pattern", 4)
    mock_set_path_value.mock_calls[1][1] == ("power", 1)


@pytest.mark.parametrize("platforms", [("light",)])
async def test_turn_off(hass, setup_evil_genius_labs):
    """Test turning off."""
    with patch("pyevilgenius.EvilGeniusDevice.set_path_value") as mock_set_path_value:
        await hass.services.async_call(
            "light",
            "turn_off",
            {
                "entity_id": "light.fibonacci256_23d4",
            },
            blocking=True,
        )

    assert len(mock_set_path_value.mock_calls) == 1
    mock_set_path_value.mock_calls[0][1] == ("power", 0)
