"""Test the Axion DMX light."""

import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.axion_dmx.light import AxionDMXLight
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ColorMode,
)
from homeassistant.core import HomeAssistant


class TestAxionDMXLight(unittest.TestCase):
    """Axion DMX Light test class."""

    @pytest.mark.asyncio
    async def setUp(self):
        """Set up the test case."""
        self.config_dir = tempfile.mkdtemp()
        self.hass = HomeAssistant(self.config_dir)
        await self.hass.async_block_till_done()
        self.api = AsyncMock()
        self.channel = 1
        self.light_type = "RGB"
        self.coordinator = AsyncMock()

        self.light = AxionDMXLight(
            self.coordinator, self.api, self.channel, self.light_type
        )

    @pytest.mark.asyncio
    async def test_name(self):
        """Test the name property."""
        assert self.light.name == "Axion Light 1"

    @pytest.mark.asyncio
    async def test_unique_id(self):
        """Test the unique_id property."""
        assert self.light.unique_id == "axion_dmx_light_1"

    @pytest.mark.asyncio
    async def test_is_on(self):
        """Test the is_on property."""
        assert not self.light.is_on

    @pytest.mark.asyncio
    async def test_brightness(self):
        """Test the brightness property."""
        assert self.light.brightness == 255

    @pytest.mark.asyncio
    async def test_color_mode(self):
        """Test the color_mode property."""
        assert self.light.color_mode == ColorMode.HS

    @patch("custom_components.axion_dmx.light.color_util.color_hs_to_RGB")
    @pytest.mark.asyncio
    async def test_hs_color(self, mock_color_hs_to_RGB):
        """Test setting and getting the HS color."""
        hs_color = (30, 100)
        mock_color_hs_to_RGB.return_value = (255, 128, 0)

        self.hass.loop.run_until_complete(
            self.light.async_turn_on(**{ATTR_HS_COLOR: hs_color})
        )

        assert self.light.hs_color == hs_color
        mock_color_hs_to_RGB.assert_called_once_with(*hs_color)
        self.api.set_color.assert_called_once_with(self.channel - 1, [255, 128, 0])

    @patch("custom_components.axion_dmx.light.color_util.color_hs_to_RGB")
    @pytest.mark.asyncio
    async def test_brightness_scaling(self, mock_color_hs_to_RGB):
        """Test the brightness scaling on RGB color."""
        hs_color = (30, 100)
        brightness = 128
        mock_color_hs_to_RGB.return_value = (255, 128, 0)

        self.hass.loop.run_until_complete(
            self.light.async_turn_on(
                **{ATTR_HS_COLOR: hs_color, ATTR_BRIGHTNESS: brightness}
            )
        )

        assert self.light.brightness == brightness
        self.api.set_color.assert_called_once_with(self.channel - 1, [128, 64, 0])

    @patch(
        "custom_components.axion_dmx.light.color_util.color_temperature_kelvin_to_mired"
    )
    @pytest.mark.asyncio
    async def test_color_temp(self, mock_kelvin_to_mired):
        """Test the color temperature setting."""
        color_temp = 4000
        mock_kelvin_to_mired.return_value = 250

        self.light._color_temp = color_temp
        assert self.light.color_temp == 250
        mock_kelvin_to_mired.assert_called_once_with(color_temp)

    @pytest.mark.asyncio
    async def test_rgbw_color(self):
        """Test setting and getting the RGBW color."""
        rgbw_color = (255, 128, 0, 64)

        self.hass.loop.run_until_complete(
            self.light.async_turn_on(**{ATTR_RGBW_COLOR: rgbw_color})
        )

        assert self.light.rgbw_color == rgbw_color
        self.api.set_rgbw.assert_called_once_with(self.channel - 1, rgbw_color)

    @pytest.mark.asyncio
    async def test_rgbww_color(self):
        """Test setting and getting the RGBWW color."""
        rgbww_color = (255, 128, 0, 64, 32)

        self.hass.loop.run_until_complete(
            self.light.async_turn_on(**{ATTR_RGBWW_COLOR: rgbww_color})
        )

        assert self.light.rgbww_color == rgbww_color
        self.api.set_rgbww.assert_called_once_with(self.channel - 1, rgbww_color)


if __name__ == "__main__":
    unittest.main()
