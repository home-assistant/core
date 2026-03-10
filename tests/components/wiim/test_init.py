"""Tests for the WiiM integration initialization."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from wiim.controller import WiimController
from wiim.wiim_device import WiimDevice

from homeassistant.components.wiim import async_setup_entry, async_unload_entry
from homeassistant.components.wiim.const import DOMAIN, PLATFORMS, WiimData
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test that async_setup_entry sets up domain data and adds the device."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.wiim.WiimController") as mock_controller_cls,
        patch(
            "homeassistant.components.wiim.async_create_wiim_device"
        ) as mock_create_wiim_device,
        patch(
            "homeassistant.components.wiim.async_get_clientsession",
            return_value=AsyncMock(),
        ),
        patch("homeassistant.components.wiim.const.PLATFORMS", []),
        patch(
            "homeassistant.components.wiim.get_url",
            return_value="http://192.168.1.10:8123",
        ),
        patch(
            "homeassistant.components.wiim.async_get_source_ip",
            return_value="192.168.1.10",
        ),
    ):
        mock_controller = MagicMock()
        mock_controller.add_device = AsyncMock()
        mock_controller.remove_device = AsyncMock()
        mock_controller_cls.return_value = mock_controller

        mock_device = MagicMock()
        mock_device.udn = "test-udn"
        mock_device.name = "Test Device"
        mock_device.disconnect = AsyncMock()
        mock_create_wiim_device.return_value = mock_device

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        mock_controller_cls.assert_called_once()
        mock_create_wiim_device.assert_awaited_once()
        mock_controller.add_device.assert_awaited_once_with(mock_device)


@pytest.mark.asyncio
async def test_async_setup_entry_device_init_failure(
    mock_hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test async_setup_entry when UPnP device creation fails -> ConfigEntryNotReady."""
    mock_config_entry.add_to_hass(mock_hass)

    with (
        patch(
            "homeassistant.components.wiim.async_create_wiim_device",
            return_value=None,
        ),
        patch(
            "homeassistant.components.wiim.async_get_clientsession",
            return_value=AsyncMock(),
        ),
        patch("homeassistant.components.wiim.WiimController") as mock_controller_class,
    ):
        mock_controller_instance = AsyncMock()
        mock_controller_class.return_value = mock_controller_instance

        with pytest.raises(
            ConfigEntryNotReady, match="Failed to initialize WiiM device"
        ):
            await async_setup_entry(mock_hass, mock_config_entry)


@pytest.mark.asyncio
async def test_async_unload_entry_success(
    mock_hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_wiim_device: WiimDevice,
    mock_wiim_controller: WiimController,
) -> None:
    """Test successful unloading of a config entry."""
    mock_config_entry.runtime_data = mock_wiim_device

    mock_hass.data[DOMAIN] = WiimData(
        controller=mock_wiim_controller,
        entity_id_to_udn_map={"media_player.test": "uuid:123"},
    )

    mock_hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    with patch.object(
        mock_hass.config_entries, "async_loaded_entries", return_value=[]
    ) as mock_loaded_entries:
        result = await async_unload_entry(mock_hass, mock_config_entry)

        assert result is True

        mock_loaded_entries.assert_called_once_with(DOMAIN)

        assert DOMAIN not in mock_hass.data

    mock_hass.config_entries.async_unload_platforms.assert_awaited_once_with(
        mock_config_entry, PLATFORMS
    )
