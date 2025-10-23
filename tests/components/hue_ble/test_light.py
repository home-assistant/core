"""Hue BLE light tests."""

from unittest.mock import AsyncMock

from homeassistant.components.hue_ble.light import HueBLELight
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_XY_COLOR,
)
from homeassistant.util import color as color_util


async def test_lights() -> None:
    """Test controlling a light."""

    mock_light = AsyncMock()
    light = HueBLELight(mock_light)

    kwargs_on = {
        ATTR_BRIGHTNESS: 100,
        ATTR_COLOR_TEMP_KELVIN: 2700,
        ATTR_XY_COLOR: (10, 10),
    }
    await light.async_turn_on(**kwargs_on)
    mock_light.set_power.assert_called_with(True)
    mock_light.set_brightness.assert_called_with(100)
    mock_light.set_colour_temp.assert_called_with(
        color_util.color_temperature_kelvin_to_mired(2700)
    )
    mock_light.set_colour_xy.assert_called_with(10, 10)

    kwargs_off = {
        ATTR_BRIGHTNESS: 50,
        ATTR_COLOR_TEMP_KELVIN: 3500,
        ATTR_XY_COLOR: (0.5, 0.5),
    }
    await light.async_turn_off(**kwargs_off)
    mock_light.set_power.assert_called_with(False)
    mock_light.set_brightness.assert_called_with(50)
    mock_light.set_colour_temp.assert_called_with(
        color_util.color_temperature_kelvin_to_mired(3500)
    )
    mock_light.set_colour_xy.assert_called_with(0.5, 0.5)
