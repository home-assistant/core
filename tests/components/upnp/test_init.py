"""Test UPnP/IGD setup process."""
from __future__ import annotations

import pytest

from homeassistant.components import ssdp
from homeassistant.components.upnp.const import (
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import TEST_DISCOVERY

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_get_source_ip")
async def test_async_setup_entry_default(hass: HomeAssistant, set_ssdp_discovery):
    """Test async_setup_entry."""
    set_ssdp_discovery(TEST_DISCOVERY)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONFIG_ENTRY_UDN: TEST_DISCOVERY[ssdp.ATTR_UPNP_UDN],
            CONFIG_ENTRY_ST: TEST_DISCOVERY[ssdp.ATTR_SSDP_ST],
        },
    )

    # Initialisation of component, no device discovered.
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Load config_entry.
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id) is True
