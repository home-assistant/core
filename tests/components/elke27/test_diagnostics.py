"""Tests for Elke27 diagnostics."""

from __future__ import annotations

from unittest.mock import Mock

from homeassistant.components.elke27.const import CONF_LINK_KEYS, DOMAIN
from homeassistant.components.elke27.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_diagnostics_redacts_sensitive_data(hass: HomeAssistant) -> None:
    """Test diagnostics redacts link keys and identifiers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.50",
            CONF_PORT: 2101,
            CONF_LINK_KEYS: {"k": "secret"},
        },
        options={
            "panel_info": {"panel_mac": "aa:bb:cc:dd:ee:ff", "panel_host": "host"},
            "table_info": {"zones": 4},
        },
    )
    entry.add_to_hass(hass)

    hub = Mock()
    hub.panel_info = {"panel_mac": "aa:bb:cc:dd:ee:ff", "panel_serial": "1234"}
    hub.table_info = {"zones": 4}
    hub.is_ready = True

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["ready"] is True
    assert diagnostics["entry_data"][CONF_LINK_KEYS] == "**REDACTED**"
    assert diagnostics["panel_info"]["panel_mac"] == "**REDACTED**"
