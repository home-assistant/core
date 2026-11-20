"""Tests for the buienradar component."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.buienradar.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

TEST_LATITUDE = 51.5288504
TEST_LONGITUDE = 5.4002156
TEST_CFG_DATA = {CONF_LATITUDE: TEST_LATITUDE, CONF_LONGITUDE: TEST_LONGITUDE}


async def setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the integration with a config entry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
