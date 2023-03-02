"""Tests for init methods."""
from unittest.mock import patch

from homeassistant.components.flipr.const import CONF_FLIPR_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "dummylogin",
            CONF_PASSWORD: "dummypass",
            CONF_FLIPR_ID: "FLIP1",
        },
        unique_id="123456",
    )
    entry.add_to_hass(hass)
    with patch("homeassistant.components.flipr.FliprAPIRestClient"):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state == ConfigEntryState.NOT_LOADED
