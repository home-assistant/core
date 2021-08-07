"""Test UPnP/IGD setup process."""
from __future__ import annotations

import pytest

from homeassistant.components import ssdp
from homeassistant.components.upnp.const import (
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DOMAIN,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.setup import async_setup_component

from .common import TEST_DISCOVERY, TEST_ST, TEST_UDN
from .mock_ssdp_scanner import mock_ssdp_scanner  # noqa: F401
from .mock_upnp_device import mock_upnp_device  # noqa: F401

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_ssdp_scanner", "mock_upnp_device")
async def test_async_setup_entry_default(hass: HomeAssistant):
    """Test async_setup_entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONFIG_ENTRY_UDN: TEST_UDN,
            CONFIG_ENTRY_ST: TEST_ST,
        },
    )

    # Initialisation of component, no device discovered.
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Device is discovered.
    ssdp_scanner: ssdp.Scanner = hass.data[ssdp.DOMAIN]
    ssdp_scanner.cache[(TEST_UDN, TEST_ST)] = TEST_DISCOVERY
    # Speed up callback in ssdp.async_register_callback.
    hass.state = CoreState.not_running

    # Load config_entry.
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id) is True
