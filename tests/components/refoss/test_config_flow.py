"""Tests for the Refoss config flow."""
from __future__ import annotations

from typing import Final
from unittest.mock import Mock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from tests.common import MockConfigEntry

DOMAIN: Final = "refoss"


async def test_configured(hass: HomeAssistant):
    """Test a successful config flow."""
    with patch(
        "homeassistant.components.refoss.config_flow.get_mac_address",
        return_value="00:11:22:33:44:55",
    ), patch("socket.socket", return_value=Mock()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "Refoss"


async def test_already_configured_abort(hass: HomeAssistant) -> None:
    """test_already_configured_abort."""
    with patch(
        "homeassistant.components.refoss.config_flow.get_mac_address",
        return_value="00:11:22:33:44:55",
    ) as mock_mac:
        mac = mock_mac.return_value

        config_entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=format_mac(mac),
            data={
                CONF_MAC: mac,
            },
            title="Refoss",
        )
        config_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"
