"""Tests for Sanix."""
from homeassistant.components.sanix.const import DOMAIN, SANIX_API_HOST

from tests.common import MockConfigEntry, load_fixture

API_URL = f"{SANIX_API_HOST}/api/measurement/read.php?serial_no=1810088&auth_token=75868dcf8ea4c64e2063f6c4e70132d2"


async def init_integration(hass, aioclient_mock) -> MockConfigEntry:
    """Set up the Sanix integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SANIX-1810088",
        entry_id="75868dcf8ea4c64e2063f6c4e70132d2",
        unique_id="1810088",
        data={"serial_no": "1810088", "token": "75868dcf8ea4c64e2063f6c4e70132d2"},
    )

    aioclient_mock.get(API_URL, text=load_fixture("authorized.json", "sanix"))
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
