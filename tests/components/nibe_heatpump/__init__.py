"""Tests for the Nibe Heat Pump integration."""

from typing import Any

from nibe.heatpump import Model

from homeassistant.components.nibe_heatpump import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_ENTRY_DATA = {
    "model": None,
    "ip_address": "127.0.0.1",
    "listening_port": 9999,
    "remote_read_port": 10000,
    "remote_write_port": 10001,
    "word_swap": True,
    "connection_type": "nibegw",
}


async def async_add_entry(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Add entry and get the coordinator."""
    entry = MockConfigEntry(domain=DOMAIN, title="Dummy", data=data)

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED


async def async_add_model(hass: HomeAssistant, model: Model):
    """Add entry of specific model."""
    await async_add_entry(hass, {**MOCK_ENTRY_DATA, "model": model.name})
