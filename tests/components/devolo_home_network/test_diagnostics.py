"""Tests for the devolo Home Network diagnostics."""
from __future__ import annotations

import pytest

from homeassistant.components.devolo_home_network.diagnostics import TO_REDACT
from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import configure_integration
from .const import DISCOVERY_INFO

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("mock_device")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test config entry diagnostics."""
    entry = configure_integration(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    entry_dict = entry.as_dict()
    for key in TO_REDACT:
        entry_dict["data"][key] = REDACTED

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert result == {
        "entry": entry_dict,
        "device_info": {
            "mt_number": DISCOVERY_INFO.properties["MT"],
            "product": DISCOVERY_INFO.properties["Product"],
            "firmware": DISCOVERY_INFO.properties["FirmwareVersion"],
            "device_api": True,
            "plcnet_api": True,
            "features": DISCOVERY_INFO.properties["Features"].split(","),
        },
    }
