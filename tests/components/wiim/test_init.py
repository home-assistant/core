"""pytest __init__.py."""

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
    mock_hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_upnp_device,
    mock_http_api: MagicMock,
) -> None:
    """Test that async_setup_entry sets up domain data and adds the device."""
    mock_hass.data = {}  # type: ignore[assignment]

    mock_config_entry.data = {
        CONF_HOST: "192.168.1.100",
        CONF_UDN: "uuid-test",
        CONF_UPNP_LOCATION: "http://192.168.1.100:49152/description.xml",
    }  # type: ignore[assignment]

    with (
        patch("homeassistant.components.wiim.UpnpFactory") as mock_factory_cls,
        patch("wiim.endpoint.WiimApiEndpoint", return_value=mock_http_api),
        patch("homeassistant.components.wiim.WiimDevice") as mock_wiim_device_cls,
        patch(
            "homeassistant.components.wiim.async_get_clientsession",
            return_value=AsyncMock(),
        ),
        patch("homeassistant.components.wiim.const.PLATFORMS", []),
        patch("wiim.controller.WiimController") as mock_controller_cls,
    ):
        factory_inst = MagicMock()
        factory_inst.async_create_device = AsyncMock(return_value=mock_upnp_device)
        mock_factory_cls.return_value = factory_inst

        wiim_dev_inst = AsyncMock()
        wiim_dev_inst._http_request = AsyncMock(return_value={"devices": []})
        mock_wiim_device_cls.return_value = wiim_dev_inst

        controller_inst = AsyncMock()
        controller_inst.add_device = AsyncMock()
        controller_inst.remove_device = AsyncMock()
        mock_controller_cls.return_value = controller_inst

        mock_hass.data[DOMAIN] = WiimData(
            controller=controller_inst,
            entity_id_to_udn_map={},
        )

        with patch.object(
            mock_hass, "async_add_executor_job", AsyncMock(return_value="192.168.1.100")
        ):
            result = await async_setup_entry(mock_hass, mock_config_entry)

        assert result is True
        assert DOMAIN in mock_hass.data
        assert mock_config_entry.runtime_data is wiim_dev_inst
        controller_inst.add_device.assert_awaited_once_with(wiim_dev_inst)


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
        entity_id_to_udn_map={"media_player.test_wiim_device": mock_wiim_device.udn},
    )

    async def mock_unload_platforms_side_effect(entry_to_unload, platforms):
        if entry_to_unload.entry_id == mock_config_entry.entry_id:
            entry_to_unload.runtime_data = None
        return True

    mock_hass.config_entries = MagicMock()
    mock_hass.config_entries.async_unload_platforms = AsyncMock(
        side_effect=mock_unload_platforms_side_effect
    )

    with patch.object(
        mock_hass.config_entries, "async_entries", new_callable=AsyncMock
    ) as mock_async_entries:
        mock_async_entries.return_value = []

    result = await async_unload_entry(mock_hass, mock_config_entry)

    assert result is True
    mock_hass.config_entries.async_unload_platforms.assert_awaited_once_with(
        mock_config_entry, PLATFORMS
    )

    assert mock_config_entry.runtime_data is None
    assert DOMAIN not in mock_hass.data
