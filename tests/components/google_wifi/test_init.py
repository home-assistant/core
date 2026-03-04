"""Tests for the google_wifi component."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.google_wifi.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the integration."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "192.168.86.1"})
    entry.add_to_hass(hass)

    with patch("homeassistant.components.google_wifi.sensor.requests.get"):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
