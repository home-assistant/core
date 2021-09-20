"""Tests for the local_ip component."""
from homeassistant.components.local_ip import DOMAIN
from homeassistant.util import get_local_ip

from tests.common import MockConfigEntry


async def test_basic_setup(hass):
    """Test component setup creates entry from config."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    local_ip = await hass.async_add_executor_job(get_local_ip)
    state = hass.states.get(f"sensor.{DOMAIN}")
    assert state
    assert state.state == local_ip
