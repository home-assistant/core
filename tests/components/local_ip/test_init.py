"""Tests for the local_ip component."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.components.local_ip import DOMAIN
from homeassistant.components.network import MDNS_TARGET_IP, async_get_source_ip
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_basic_setup(hass: HomeAssistant, mock_get_source_ip) -> None:
    """Test component setup creates entry from config."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == config_entries.ConfigEntryState.LOADED

    local_ip = await async_get_source_ip(hass, target_ip=MDNS_TARGET_IP)
    state = hass.states.get(f"sensor.{DOMAIN}")
    assert state
    assert state.state == local_ip

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
