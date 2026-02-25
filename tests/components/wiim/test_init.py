"""pytest __init__.py."""

import asyncio
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, patch

from async_upnp_client.exceptions import UpnpConnectionError
import pytest
from wiim.controller import WiimController
from wiim.wiim_device import WiimDevice

from homeassistant.components.wiim import async_setup_entry, async_unload_entry
from homeassistant.components.wiim.const import (
    CONF_UDN,
    CONF_UPNP_LOCATION,
    DOMAIN,
    PLATFORMS,
    WiimData,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_upnp_device,
    mock_http_api: MagicMock,
) -> None:
    """Test that async_setup_entry sets up domain data and adds the device."""
    mock_config_entry.setup_lock = asyncio.Lock()
    mock_config_entry.data = {
        CONF_HOST: "192.168.1.100",
        CONF_UDN: "uuid-test",
        CONF_UPNP_LOCATION: "http://192.168.1.100:49152/description.xml",
    }

    with (
        patch("homeassistant.components.wiim.WiimController") as mock_controller_cls,
        patch("homeassistant.components.wiim.UpnpFactory") as mock_factory_cls,
        patch("wiim.endpoint.WiimApiEndpoint", return_value=mock_http_api),
        patch("homeassistant.components.wiim.WiimDevice") as mock_wiim_device_cls,
        patch(
            "homeassistant.components.wiim.async_get_clientsession",
            return_value=AsyncMock(),
        ),
        patch("homeassistant.components.wiim.const.PLATFORMS", []),
    ):
        mock_controller = MagicMock()
        mock_controller.add_device = AsyncMock()
        mock_controller_cls.return_value = mock_controller

        mock_device = AsyncMock()
        mock_device.friendly_name = "Test Device"
        mock_device.disconnect = AsyncMock()
        mock_wiim_device_cls.return_value = mock_device

        factory_inst = MagicMock()
        factory_inst.async_create_device = AsyncMock(return_value=mock_device)
        mock_factory_cls.return_value = factory_inst

        result = await async_setup_entry(hass, mock_config_entry)

        assert result is True
        assert DOMAIN in hass.data
        assert isinstance(hass.data[DOMAIN].controller, MagicMock)

        mock_controller.add_device.assert_awaited_once_with(mock_device)
        mock_device.disconnect.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_setup_entry_device_init_failure(
    mock_hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test async_setup_entry when UPnP device creation fails -> ConfigEntryNotReady."""

    config_entry_data = {
        CONF_HOST: "192.168.1.100",
        CONF_UDN: "uuid:test-device",
        CONF_UPNP_LOCATION: "http://192.168.1.100:49152/description.xml",
    }

    mock_config_entry.data = MappingProxyType(config_entry_data)

    with (
        patch("homeassistant.components.wiim.UpnpFactory") as mock_factory_class,
        patch("wiim.endpoint.WiimApiEndpoint"),
        patch("wiim.wiim_device.WiimDevice"),
        patch(
            "homeassistant.components.wiim.async_get_clientsession",
            return_value=AsyncMock(),
        ),
        patch("wiim.controller.WiimController") as mock_controller_class,
    ):
        mock_factory_instance = MagicMock()
        mock_factory_instance.async_create_device = AsyncMock(
            side_effect=UpnpConnectionError("UPnP timeout")
        )
        mock_factory_class.return_value = mock_factory_instance

        mock_controller_instance = AsyncMock()
        mock_controller_class.return_value = mock_controller_instance

        with pytest.raises(
            ConfigEntryNotReady, match="Failed to connect to UPnP device"
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
