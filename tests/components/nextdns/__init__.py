"""Tests for the NextDNS integration."""
from unittest.mock import patch

from homeassistant.components.nextdns.const import CONF_PROFILE_ID, DOMAIN
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry

PROFILES = [{"id": "xyz12", "fingerprint": "aabbccdd123", "name": "Fake Profile"}]


async def init_integration(hass) -> MockConfigEntry:
    """Set up the NextDNS integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Fake Profile",
        unique_id="xyz12",
        data={CONF_API_KEY: "fake_api_key", CONF_PROFILE_ID: "xyz12"},
    )

    with patch(
        "homeassistant.components.nextdns.NextDns.get_profiles", return_value=PROFILES
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
