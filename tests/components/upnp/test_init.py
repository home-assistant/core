"""Test UPnP/IGD setup process."""

from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components import ssdp
from homeassistant.components.upnp.const import (
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DOMAIN,
)
from homeassistant.components.upnp.device import Device
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .mock_device import MockDevice

from tests.common import MockConfigEntry


async def test_async_setup_entry_default(hass: HomeAssistant):
    """Test async_setup_entry."""
    udn = "uuid:device_1"
    location = "http://192.168.1.1/desc.xml"
    mock_device = MockDevice(udn)
    discovery = {
        ssdp.ATTR_SSDP_LOCATION: location,
        ssdp.ATTR_SSDP_ST: mock_device.device_type,
        ssdp.ATTR_UPNP_UDN: mock_device.udn,
        ssdp.ATTR_SSDP_USN: mock_device.usn,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONFIG_ENTRY_UDN: mock_device.udn,
            CONFIG_ENTRY_ST: mock_device.device_type,
        },
    )

    config = {
        # no upnp
    }
    async_create_device = AsyncMock(return_value=mock_device)
    mock_get_discovery = Mock()
    with patch.object(Device, "async_create_device", async_create_device), patch.object(
        ssdp, "async_get_discovery_info_by_udn_st", mock_get_discovery
    ):
        # initialisation of component, no device discovered
        mock_get_discovery.return_value = None
        await async_setup_component(hass, "upnp", config)
        await hass.async_block_till_done()

        # loading of config_entry, device discovered
        mock_get_discovery.return_value = discovery
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id) is True

        # ensure device is stored/used
        async_create_device.assert_called_with(hass, discovery[ssdp.ATTR_SSDP_LOCATION])
