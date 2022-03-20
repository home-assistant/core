"""Test UPnP/IGD setup process."""
from __future__ import annotations

import pytest

from homeassistant.components import ssdp
from homeassistant.components.upnp import UpnpDataUpdateCoordinator
from homeassistant.components.upnp.const import (
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DOMAIN,
)
from homeassistant.components.upnp.device import Device
from homeassistant.core import HomeAssistant

from .conftest import TEST_DISCOVERY, TEST_ST, TEST_UDN

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("ssdp_instant_discovery", "mock_get_source_ip")
async def test_async_setup_entry_default(hass: HomeAssistant):
    """Test async_setup_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ST: TEST_ST,
        },
    )

    # Load config_entry.
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id) is True


async def test_reinitialize_device(
    hass: HomeAssistant, setup_integration: MockConfigEntry
):
    """Test device is reinitialized when device changes location."""
    config_entry = setup_integration
    coordinator: UpnpDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    device: Device = coordinator.device
    assert device._igd_device.device.device_url == TEST_DISCOVERY.ssdp_location

    # Reinit.
    new_location = "http://192.168.1.1:12345/desc.xml"
    await device.async_ssdp_callback(
        ssdp.SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://192.168.1.1:12345/desc.xml",
            upnp={},
        ),
        ...,
    )
    assert device._igd_device.device.device_url == new_location
