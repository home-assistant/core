"""Tessie common helpers for tests."""

from homeassistant.components.tessie.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

TEST_VEHICLES = load_fixture("vehicles.json", DOMAIN)
TEST_DATA = {CONF_API_KEY: "1234567890"}
URL_VEHICLES = "https://api.tessie.com/vehicles"


async def setup_platform(hass: HomeAssistant, side_effect=None):
    """Set up the Tessie platform."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_DATA,
        unique_id=TEST_DATA[CONF_API_KEY],
    )
    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    return mock_entry
