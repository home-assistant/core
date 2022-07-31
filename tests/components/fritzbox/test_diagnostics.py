"""Tests for the AVM Fritz!Box integration."""
from __future__ import annotations

from unittest.mock import Mock

from aiohttp import ClientSession

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.fritzbox.const import DOMAIN as FB_DOMAIN
from homeassistant.components.fritzbox.diagnostics import TO_REDACT
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant

from . import setup_config_entry
from .const import MOCK_CONFIG

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSession, fritz: Mock
):
    """Test config entry diagnostics."""
    assert await setup_config_entry(hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0])

    entries = hass.config_entries.async_entries(FB_DOMAIN)
    entry_dict = entries[0].as_dict()
    for key in TO_REDACT:
        entry_dict["data"][key] = REDACTED

    result = await get_diagnostics_for_config_entry(hass, hass_client, entries[0])

    assert result == {"entry": entry_dict, "data": {}}
