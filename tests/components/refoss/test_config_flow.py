"""Tests for the Refoss config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from refoss_ha.const import DOMAIN
from refoss_ha.util import get_mac_address

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test  configuration if refoss not configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

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
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test  configuration if refoss already configured."""

    mac = get_mac_address()
    entry = MockConfigEntry(domain=DOMAIN, unique_id=mac)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_MAC: mac},
    )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
