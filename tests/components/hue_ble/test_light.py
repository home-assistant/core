"""Hue BLE light tests."""

from unittest.mock import AsyncMock, PropertyMock, patch

from HueBLE import HueBleLight
import pytest

from homeassistant.components.hue_ble.light import HueBLELight
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_XY_COLOR,
    ColorMode,
)
from homeassistant.util import color as color_util

from . import TEST_DEVICE_MAC, TEST_DEVICE_NAME

from tests.components.bluetooth import generate_ble_device


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

    await light.async_turn_off()
    mock_light.set_power.assert_called_with(False)


@pytest.mark.parametrize(
    (
        "mock_supports_brightness",
        "mock_supports_color_temp",
        "mock_supports_color_xy",
        "mock_color_temp_mode",
        "color_mode",
    ),
    [
        (True, True, True, False, ColorMode.XY),
        (True, True, True, True, ColorMode.COLOR_TEMP),
        (True, True, False, True, ColorMode.COLOR_TEMP),
        (True, False, False, False, ColorMode.BRIGHTNESS),
        (False, False, False, False, ColorMode.ONOFF),
    ],
    ids=[
        "xy_light_in_xy",
        "xy_light_in_color_temp",
        "ct_light_in_color_temp",
        "brightness_only_light",
        "on_off_only_light",
    ],
)
async def test_color(
    mock_supports_brightness: bool,
    mock_supports_color_temp: bool,
    mock_supports_color_xy: bool,
    mock_color_temp_mode: bool,
    color_mode: ColorMode,
) -> None:
    """Test the color mode behavior."""

    light = HueBLELight(
        HueBleLight(generate_ble_device(TEST_DEVICE_NAME, TEST_DEVICE_MAC))
    )

    with (
        patch(
            "homeassistant.components.hue_ble.light.HueBleLight.supports_on_off",
            new_callable=PropertyMock,
            return_value=True,
        ),
        patch(
            "homeassistant.components.hue_ble.light.HueBleLight.supports_brightness",
            new_callable=PropertyMock,
            return_value=mock_supports_brightness,
        ),
        patch(
            "homeassistant.components.hue_ble.light.HueBleLight.supports_colour_temp",
            new_callable=PropertyMock,
            return_value=mock_supports_color_temp,
        ),
        patch(
            "homeassistant.components.hue_ble.light.HueBleLight.supports_colour_xy",
            new_callable=PropertyMock,
            return_value=mock_supports_color_xy,
        ),
        patch(
            "homeassistant.components.hue_ble.light.HueBleLight.colour_temp_mode",
            new_callable=PropertyMock,
            return_value=mock_color_temp_mode,
        ),
    ):
        assert light.color_mode is color_mode
