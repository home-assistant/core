"""Test Sensibo diagnostics."""
from __future__ import annotations

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(
    hass: HomeAssistant, hass_client: aiohttp.client, load_int: ConfigEntry
):
    """Test generating diagnostics for a config entry."""
    entry = load_int

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diag["status"] == "success"
    for device in diag["result"]:
        assert device["id"] == "**REDACTED**"
        assert device["qrId"] == "**REDACTED**"
        assert device["macAddress"] == "**REDACTED**"
        assert device["location"] == "**REDACTED**"
        assert device["productModel"] in ["skyv2", "pure"]
