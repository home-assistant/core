"""Test the pjlink integration."""

from homeassistant.components.pjlink.const import DEFAULT_PORT, DOMAIN

from tests.common import HomeAssistant, MockConfigEntry


async def setup_pjlink_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up PJLink integration via config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "127.0.0.1", "port": DEFAULT_PORT},
        title="test",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry
