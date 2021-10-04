"""Test UPnP/IGD setup process."""
from __future__ import annotations

import pytest

from homeassistant.components.upnp.const import (
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import TEST_ST, TEST_UDN

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

    # Initialisation of component, no device discovered.
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Load config_entry.
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id) is True
