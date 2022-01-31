"""Tests for AVM Fritz!Box diagnostics."""
from __future__ import annotations

from unittest.mock import patch

from aiohttp import ClientSession

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.fritzbox.const import DOMAIN
from homeassistant.components.fritzbox.diagnostics import TO_REDACT
from homeassistant.core import HomeAssistant

from .const import MOCK_USER_DATA

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSession, fc_class_mock, mock_get_source_ip
):
    """Test config entry diagnostics."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA, unique_id="any")
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritz.common.FritzConnection",
        side_effect=fc_class_mock,
    ), patch("homeassistant.components.fritz.common.FritzStatus"), patch(
        "homeassistant.components.fritz.common.FritzBoxTools"
    ):
        result = await hass.config_entries.async_setup(mock_config.entry_id)
        await hass.async_block_till_done()
        assert result

    entries = hass.config_entries.async_entries(DOMAIN)
    entry_dict = entries[0].as_dict()
    for key in TO_REDACT:
        entry_dict["data"][key] = REDACTED

    result = await get_diagnostics_for_config_entry(hass, hass_client, entries[0])

    assert result == {"entry": entry_dict, "device_info": {}}
