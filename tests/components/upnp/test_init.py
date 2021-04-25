"""Test UPnP/IGD setup process."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.upnp.const import (
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DISCOVERY_HOSTNAME,
    DISCOVERY_LOCATION,
    DISCOVERY_NAME,
    DISCOVERY_ST,
    DISCOVERY_UDN,
    DISCOVERY_UNIQUE_ID,
    DISCOVERY_USN,
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
    discoveries = [
        {
            DISCOVERY_LOCATION: location,
            DISCOVERY_NAME: mock_device.name,
            DISCOVERY_ST: mock_device.device_type,
            DISCOVERY_UDN: mock_device.udn,
            DISCOVERY_UNIQUE_ID: mock_device.unique_id,
            DISCOVERY_USN: mock_device.usn,
            DISCOVERY_HOSTNAME: mock_device.hostname,
        }
    ]
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
    async_discover = AsyncMock()
    with patch.object(Device, "async_create_device", async_create_device), patch.object(
        Device, "async_discover", async_discover
    ):
        # initialisation of component, no device discovered
        async_discover.return_value = []
        await async_setup_component(hass, "upnp", config)
        await hass.async_block_till_done()

        # loading of config_entry, device discovered
        async_discover.return_value = discoveries
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id) is True

        # ensure device is stored/used
        async_create_device.assert_called_with(hass, discoveries[0][DISCOVERY_LOCATION])


async def test_sync_setup_entry_multiple_discoveries(hass: HomeAssistant):
    """Test async_setup_entry."""
    udn_0 = "uuid:device_1"
    location_0 = "http://192.168.1.1/desc.xml"
    mock_device_0 = MockDevice(udn_0)
    udn_1 = "uuid:device_2"
    location_1 = "http://192.168.1.2/desc.xml"
    mock_device_1 = MockDevice(udn_1)
    discoveries = [
        {
            DISCOVERY_LOCATION: location_0,
            DISCOVERY_NAME: mock_device_0.name,
            DISCOVERY_ST: mock_device_0.device_type,
            DISCOVERY_UDN: mock_device_0.udn,
            DISCOVERY_UNIQUE_ID: mock_device_0.unique_id,
            DISCOVERY_USN: mock_device_0.usn,
            DISCOVERY_HOSTNAME: mock_device_0.hostname,
        },
        {
            DISCOVERY_LOCATION: location_1,
            DISCOVERY_NAME: mock_device_1.name,
            DISCOVERY_ST: mock_device_1.device_type,
            DISCOVERY_UDN: mock_device_1.udn,
            DISCOVERY_UNIQUE_ID: mock_device_1.unique_id,
            DISCOVERY_USN: mock_device_1.usn,
            DISCOVERY_HOSTNAME: mock_device_1.hostname,
        },
    ]
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONFIG_ENTRY_UDN: mock_device_1.udn,
            CONFIG_ENTRY_ST: mock_device_1.device_type,
        },
    )

    config = {
        # no upnp
    }
    async_create_device = AsyncMock(return_value=mock_device_1)
    async_discover = AsyncMock()
    with patch.object(Device, "async_create_device", async_create_device), patch.object(
        Device, "async_discover", async_discover
    ):
        # initialisation of component, no device discovered
        async_discover.return_value = []
        await async_setup_component(hass, "upnp", config)
        await hass.async_block_till_done()

        # loading of config_entry, device discovered
        async_discover.return_value = discoveries
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id) is True

        # ensure device is stored/used
        async_create_device.assert_called_with(hass, discoveries[1][DISCOVERY_LOCATION])
