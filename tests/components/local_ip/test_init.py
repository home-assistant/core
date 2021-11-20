"""Tests for the local_ip component."""
from homeassistant.components.local_ip import DOMAIN
from homeassistant.components.network import async_get_source_ip
from homeassistant.components.zeroconf import MDNS_TARGET_IP

from tests.common import MockConfigEntry


async def test_basic_setup(hass, mock_get_source_ip):
    """Test component setup creates entry from config."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    local_ip = await async_get_source_ip(hass, target_ip=MDNS_TARGET_IP)
    state = hass.states.get(f"sensor.{DOMAIN}")
    assert state
    assert state.state == local_ip
