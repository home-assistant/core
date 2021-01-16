"""Test the Cisco Webex config flow."""

from homeassistant.components.cisco_webex import (
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.cisco_webex.const import DOMAIN

from tests.common import MockConfigEntry
from tests.components.cisco_webex.mocks import MockWebexTeamsAPI

TEST_DATA = {"email": "fff@fff.com"}

MOCK_API = MockWebexTeamsAPI(access_token="123")
MOCK_CONFIG = {"token": "123", "email": "ff@ff.com"}
MOCK_CONFIG_ENTRY = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id="0923")


async def test_init_setup(hass):
    """Test init setup method."""
    setup_result = await async_setup(hass, MOCK_CONFIG)
    assert setup_result is True


async def test_init_setup_entry(hass):
    """Test init setup entry method."""
    hass.data.setdefault(DOMAIN, {})
    setup_entry_result = await async_setup_entry(hass, MOCK_CONFIG_ENTRY)
    assert setup_entry_result is True


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    MOCK_CONFIG_ENTRY.add_to_hass(hass)
    await hass.config_entries.async_setup(MOCK_CONFIG_ENTRY.entry_id)
    await hass.async_block_till_done()

    assert hass.data[DOMAIN]

    assert await async_unload_entry(hass, MOCK_CONFIG_ENTRY)
    assert not hass.data[DOMAIN]
