"""Tests for the Refoss config flow."""
from __future__ import annotations

from refoss_ha.const import DOMAIN
from refoss_ha.util import get_mac_address

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_configured(hass: HomeAssistant):
    """Test  configuration if refoss already configured."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    # ha Host MAC address
    mac = get_mac_address()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"mac": mac},
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test  configuration if refoss already configured."""
    mac = get_mac_address()
    entry = MockConfigEntry(domain=DOMAIN, unique_id=mac)

    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"mac": mac},
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
