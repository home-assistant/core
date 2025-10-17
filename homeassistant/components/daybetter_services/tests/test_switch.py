"""Test the DayBetter switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


@pytest.fixture
def mock_switch_device():
    """Create a mock switch device."""
    return {
        "deviceId": "switch_001",
        "deviceName": "Test Switch",
        "deviceType": "switch",
        "online": True,
        "isOn": False,
    }


@pytest.mark.asyncio
async def test_async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, mock_switch_device
):
    """Test switch platform setup."""
    # Setup hass.data
    mock_api = AsyncMock()
    hass.data[DOMAIN] = {
        config_entry.entry_id: {"api": mock_api, "devices": [mock_switch_device]}
    }

    with patch(
        "homeassistant.components.daybetter_services.switch.DayBetterSwitch"
    ) as mock_switch_class:
        mock_switch = MagicMock()
        mock_switch_class.return_value = mock_switch

        from homeassistant.components.daybetter_services.switch import async_setup_entry

        async_add_entities = AsyncMock()
        await async_setup_entry(hass, config_entry, async_add_entities)

        async_add_entities.assert_called_once()
        mock_switch_class.assert_called_once()


class TestDayBetterSwitch:
    """Test the DayBetterSwitch entity."""

    @pytest.fixture
    def switch_entity(self, mock_switch_device):
        """Create a DayBetterSwitch entity."""
        from homeassistant.components.daybetter_services.switch import DayBetterSwitch

        mock_api = AsyncMock()
        mock_hass = MagicMock()
        mock_entry = MagicMock()
        mock_entry.entry_id = "test_entry_id"

        return DayBetterSwitch(mock_hass, mock_entry, mock_api, mock_switch_device)

    def test_name(self, switch_entity):
        """Test switch name."""
        assert switch_entity.name == "Test Switch"

    def test_unique_id(self, switch_entity):
        """Test switch unique ID."""
        assert switch_entity.unique_id == "daybetter_switch_001"

    def test_device_info(self, switch_entity):
        """Test device info."""
        device_info = switch_entity.device_info
        assert device_info["identifiers"] == {("daybetter", "switch_001")}
        assert device_info["name"] == "Test Switch"
        assert device_info["manufacturer"] == "DayBetter"

    def test_is_on(self, switch_entity):
        """Test is_on property."""
        assert switch_entity.is_on is False

    def test_available(self, switch_entity):
        """Test available property."""
        assert switch_entity.available is True

    @pytest.mark.asyncio
    async def test_async_turn_on(self, switch_entity):
        """Test turning on."""
        with patch.object(switch_entity, "_async_control_device") as mock_control:
            mock_control.return_value = {"code": 1}

            await switch_entity.async_turn_on()

            mock_control.assert_called_once_with(device_name="Test Switch", action=True)

    @pytest.mark.asyncio
    async def test_async_turn_off(self, switch_entity):
        """Test turning off."""
        with patch.object(switch_entity, "_async_control_device") as mock_control:
            mock_control.return_value = {"code": 1}

            await switch_entity.async_turn_off()

            mock_control.assert_called_once_with(
                device_name="Test Switch", action=False
            )

    @pytest.mark.asyncio
    async def test_async_control_device_success(self, switch_entity):
        """Test successful device control."""
        mock_api = switch_entity._api
        mock_api.control_device = AsyncMock(return_value={"code": 1})

        result = await switch_entity._async_control_device(
            device_name="Test Switch", action=True
        )

        assert result is True
        mock_api.control_device.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_control_device_failure(self, switch_entity):
        """Test failed device control."""
        mock_api = switch_entity._api
        mock_api.control_device = AsyncMock(return_value={"code": 0})

        result = await switch_entity._async_control_device(
            device_name="Test Switch", action=True
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_async_control_device_exception(self, switch_entity):
        """Test device control with exception."""
        mock_api = switch_entity._api
        mock_api.control_device = AsyncMock(side_effect=Exception("Network error"))

        result = await switch_entity._async_control_device(
            device_name="Test Switch", action=True
        )

        assert result is False

    def test_update_from_device_data(self, switch_entity):
        """Test updating entity from device data."""
        new_device_data = {
            "deviceId": "switch_001",
            "deviceName": "Test Switch",
            "deviceType": "switch",
            "online": True,
            "isOn": True,
        }

        switch_entity.update_from_device_data(new_device_data)

        assert switch_entity._is_on is True
        assert switch_entity._available is True
