"""Test UPnP/IGD setup process."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.upnp.const import (
    CONFIG_ENTRY_LOCATION,
    CONFIG_ENTRY_MAC_ADDRESS,
    CONFIG_ENTRY_ORIGINAL_UDN,
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from .conftest import TEST_LOCATION, TEST_MAC_ADDRESS, TEST_ST, TEST_UDN, TEST_USN

from tests.common import MockConfigEntry


@pytest.mark.usefixtures(
    "ssdp_instant_discovery", "mock_get_source_ip", "mock_mac_address_from_host"
)
async def test_async_setup_entry_default(hass: HomeAssistant) -> None:
    """Test async_setup_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        },
    )

    # Load config_entry.
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id) is True


@pytest.mark.usefixtures(
    "ssdp_instant_discovery", "mock_get_source_ip", "mock_no_mac_address_from_host"
)
async def test_async_setup_entry_default_no_mac_address(hass: HomeAssistant) -> None:
    """Test async_setup_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_MAC_ADDRESS: None,
        },
    )

    # Load config_entry.
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id) is True


@pytest.mark.usefixtures(
    "ssdp_instant_discovery_multi_location",
    "mock_get_source_ip",
    "mock_mac_address_from_host",
)
async def test_async_setup_entry_multi_location(
    hass: HomeAssistant, mock_async_create_device: AsyncMock
) -> None:
    """Test async_setup_entry for a device both seen via IPv4 and IPv6.

    The resulting IPv4 location is preferred/stored.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USN,
        data={
            CONFIG_ENTRY_ST: TEST_ST,
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ORIGINAL_UDN: TEST_UDN,
            CONFIG_ENTRY_LOCATION: TEST_LOCATION,
            CONFIG_ENTRY_MAC_ADDRESS: TEST_MAC_ADDRESS,
        },
    )

    # Load config_entry.
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id) is True

    # Ensure that the IPv4 location is used.
    mock_async_create_device.assert_called_once_with(TEST_LOCATION)
