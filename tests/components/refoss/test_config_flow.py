"""Tests for the Refoss config flow."""
from __future__ import annotations

import pytest
from refoss_ha.const import DOMAIN
from refoss_ha.util import get_mac_address

from homeassistant import config_entries
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.skip
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test  configuration if refoss not configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
    )
    await hass.async_block_till_done()
    mac = get_mac_address()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Refoss"
    assert result2["data"] == {
        CONF_MAC: mac,
    }
