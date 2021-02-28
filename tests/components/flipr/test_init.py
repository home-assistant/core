"""Tests for init methods."""
from unittest.mock import patch

from homeassistant.components.flipr.const import (
    CONF_FLIPR_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)
from homeassistant.config_entries import ENTRY_STATE_NOT_LOADED
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant):
    """Test unload entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "dummylogin",
            CONF_PASSWORD: "ENCRYPTED_DATA_ah_ah",
            CONF_FLIPR_ID: "FLIP_Entered",
        },
        unique_id="123456",
    )
    entry.add_to_hass(hass)
    with patch("homeassistant.components.flipr.FliprAPIRestClient"), patch(
        "homeassistant.components.flipr.decrypt_data",
        return_value="DECRYPTED_DATA_ah_ah",
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.async_unload(entry.entry_id)
        assert entry.state == ENTRY_STATE_NOT_LOADED
