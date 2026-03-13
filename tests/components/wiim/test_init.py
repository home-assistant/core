"""Tests for the WiiM integration initialization."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from wiim.controller import WiimController
from wiim.exceptions import WiimDeviceException
from wiim.wiim_device import WiimDevice

from homeassistant.components.wiim import async_setup_entry, async_unload_entry
from homeassistant.components.wiim.const import DATA_WIIM, DOMAIN, PLATFORMS
from homeassistant.components.wiim.models import WiimData
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test that async_setup_entry sets up domain data and adds the device."""
    mock_config_entry.add_to_hass(hass)
    mock_session = AsyncMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)

    with (
        patch("homeassistant.components.wiim.WiimController") as mock_controller_cls,
        patch(
            "homeassistant.components.wiim.async_create_wiim_device"
        ) as mock_create_wiim_device,
        patch(
            "homeassistant.components.wiim.async_get_clientsession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.wiim.get_url",
            return_value="http://192.168.1.10:8123",
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

        result = await async_setup_entry(hass, mock_config_entry)

        assert result is True
        mock_controller_cls.assert_called_once_with(mock_session)
        assert hass.data[DATA_WIIM] == WiimData(controller=mock_controller)
        mock_create_wiim_device.assert_awaited_once_with(
            "http://192.168.1.100:49152/description.xml",
            mock_session,
            host="192.168.1.100",
            local_host="192.168.1.10",
            polling_interval=60,
        )
        mock_controller.add_device.assert_awaited_once_with(mock_device)
        hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
            mock_config_entry, PLATFORMS
        )


@pytest.mark.asyncio
async def test_async_setup_entry_device_init_failure(
    mock_hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test async_setup_entry when device initialization fails."""
    mock_config_entry.add_to_hass(mock_hass)
    mock_session = AsyncMock()

    with (
        patch(
            "homeassistant.components.wiim.async_create_wiim_device",
            side_effect=WiimDeviceException("Failed to initialize WiiM device"),
        ),
        patch(
            "homeassistant.components.wiim.async_get_clientsession",
            return_value=mock_session,
        ),
        patch("homeassistant.components.wiim.WiimController") as mock_controller_class,
        patch(
            "homeassistant.components.wiim.get_url",
            return_value="http://192.168.1.10:8123",
        ),
    ):
        mock_controller_instance = AsyncMock()
        mock_controller_class.return_value = mock_controller_instance

        assert not await async_setup_entry(mock_hass, mock_config_entry)


@pytest.mark.asyncio
async def test_async_unload_entry_success(
    mock_hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_wiim_device: WiimDevice,
    mock_wiim_controller: WiimController,
) -> None:
    """Test successful unloading of a config entry."""
    mock_config_entry.runtime_data = mock_wiim_device

    mock_hass.data[DATA_WIIM] = WiimData(
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

        assert DATA_WIIM not in mock_hass.data

    mock_hass.config_entries.async_unload_platforms.assert_awaited_once_with(
        mock_config_entry, PLATFORMS
    )
