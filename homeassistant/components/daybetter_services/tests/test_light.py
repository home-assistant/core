"""Test the DayBetter light platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.light import ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


@pytest.fixture
def mock_light_device():
    """Create a mock light device."""
    return {
        "deviceId": "light_001",
        "deviceName": "Test Light",
        "deviceType": "light",
        "online": True,
        "brightness": 128,
        "colorTemp": 4000,
        "hsColor": [180.0, 50.0],
        "isOn": True,
    }


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, mock_light_device
):
    """Test light platform setup."""
    # Setup hass.data
    mock_api = AsyncMock()
    hass.data[DOMAIN] = {
        config_entry.entry_id: {"api": mock_api, "devices": [mock_light_device]}
    }

    with patch(
        "homeassistant.components.daybetter_services.light.DayBetterLight"
    ) as mock_light_class:
        mock_light = MagicMock()
        mock_light_class.return_value = mock_light

        from homeassistant.components.daybetter_services.light import async_setup_entry

        async_add_entities = AsyncMock()
        await async_setup_entry(hass, config_entry, async_add_entities)

        async_add_entities.assert_called_once()
        mock_light_class.assert_called_once()


class TestDayBetterLight:
    """Test the DayBetterLight entity."""

    @pytest.fixture
    def light_entity(self, mock_light_device):
        """Create a DayBetterLight entity."""
        from homeassistant.components.daybetter_services.light import DayBetterLight

        mock_api = AsyncMock()
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry_id"

        return DayBetterLight(mock_hass, mock_entry, mock_api, mock_light_device)

    def test_name(self, light_entity):
        """Test light name."""
        assert light_entity.name == "Test Light"

    def test_unique_id(self, light_entity):
        """Test light unique ID."""
        assert light_entity.unique_id == "daybetter_light_001"

    def test_device_info(self, light_entity):
        """Test device info."""
        device_info = light_entity.device_info
        assert device_info["identifiers"] == {("daybetter", "light_001")}
        assert device_info["name"] == "Test Light"
        assert device_info["manufacturer"] == "DayBetter"

    def test_supported_color_modes(self, light_entity):
        """Test supported color modes."""
        expected_modes = {ColorMode.BRIGHTNESS, ColorMode.COLOR_TEMP, ColorMode.HS}
        assert light_entity.supported_color_modes == expected_modes

    def test_brightness(self, light_entity):
        """Test brightness property."""
        assert light_entity.brightness == 128

    def test_color_temp_kelvin(self, light_entity):
        """Test color temperature property."""
        assert light_entity.color_temp_kelvin == 4000

    def test_hs_color(self, light_entity):
        """Test HS color property."""
        assert light_entity.hs_color == (180.0, 50.0)

    def test_is_on(self, light_entity):
        """Test is_on property."""
        assert light_entity.is_on is True

    def test_available(self, light_entity):
        """Test available property."""
        assert light_entity.available is True

    @pytest.mark.asyncio
    async def test_async_turn_on_brightness(self, light_entity):
        """Test turning on with brightness."""
        with patch.object(light_entity, "_async_control_device") as mock_control:
            mock_control.return_value = {"code": 1}

            await light_entity.async_turn_on(brightness=255)

            mock_control.assert_called_once_with(
                device_name="Test Light",
                action=True,
                brightness=255,
                hs_color=None,
                color_temp=None,
            )

    @pytest.mark.asyncio
    async def test_async_turn_on_color_temp(self, light_entity):
        """Test turning on with color temperature."""
        with patch.object(light_entity, "_async_control_device") as mock_control:
            mock_control.return_value = {"code": 1}

            await light_entity.async_turn_on(color_temp_kelvin=3000)

            mock_control.assert_called_once_with(
                device_name="Test Light",
                action=True,
                brightness=None,
                hs_color=None,
                color_temp=3000,
            )

    @pytest.mark.asyncio
    async def test_async_turn_on_hs_color(self, light_entity):
        """Test turning on with HS color."""
        with patch.object(light_entity, "_async_control_device") as mock_control:
            mock_control.return_value = {"code": 1}

            await light_entity.async_turn_on(hs_color=(120.0, 75.0))

            mock_control.assert_called_once_with(
                device_name="Test Light",
                action=True,
                brightness=None,
                hs_color=(120.0, 75.0),
                color_temp=None,
            )

    @pytest.mark.asyncio
    async def test_async_turn_off(self, light_entity):
        """Test turning off."""
        with patch.object(light_entity, "_async_control_device") as mock_control:
            mock_control.return_value = {"code": 1}

            await light_entity.async_turn_off()

            mock_control.assert_called_once_with(
                device_name="Test Light",
                action=False,
                brightness=None,
                hs_color=None,
                color_temp=None,
            )

    @pytest.mark.asyncio
    async def test_async_control_device_success(self, light_entity):
        """Test successful device control."""
        mock_api = light_entity._api
        mock_api.control_device = AsyncMock(return_value={"code": 1})

        result = await light_entity._async_control_device(
            device_name="Test Light",
            action=True,
            brightness=128,
            hs_color=None,
            color_temp=None,
        )

        assert result is True
        mock_api.control_device.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_control_device_failure(self, light_entity):
        """Test failed device control."""
        mock_api = light_entity._api
        mock_api.control_device = AsyncMock(return_value={"code": 0})

        result = await light_entity._async_control_device(
            device_name="Test Light",
            action=True,
            brightness=128,
            hs_color=None,
            color_temp=None,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_async_control_device_exception(self, light_entity):
        """Test device control with exception."""
        mock_api = light_entity._api
        mock_api.control_device = AsyncMock(side_effect=Exception("Network error"))

        result = await light_entity._async_control_device(
            device_name="Test Light",
            action=True,
            brightness=128,
            hs_color=None,
            color_temp=None,
        )

        assert result is False

    def test_update_from_device_data(self, light_entity):
        """Test updating entity from device data."""
        new_device_data = {
            "deviceId": "light_001",
            "deviceName": "Test Light",
            "deviceType": "light",
            "online": True,
            "brightness": 200,
            "colorTemp": 5000,
            "hsColor": [240.0, 80.0],
            "isOn": False,
        }

        light_entity.update_from_device_data(new_device_data)

        assert light_entity._brightness == 200
        assert light_entity._color_temp_kelvin == 5000
        assert light_entity._hs_color == (240.0, 80.0)
        assert light_entity._is_on is False
        assert light_entity._available is True
