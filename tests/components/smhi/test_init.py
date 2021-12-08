"""Test SMHI component setup process."""
from smhi.smhi_lib import APIURL_TEMPLATE

from homeassistant.components.smhi.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import ENTITY_ID, TEST_CONFIG

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, api_response: str
) -> None:
    """Test setup entry."""
    uri = APIURL_TEMPLATE.format(TEST_CONFIG["longitude"], TEST_CONFIG["latitude"])
    aioclient_mock.get(uri, text=api_response)
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state


async def test_remove_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, api_response: str
) -> None:
    """Test remove entry."""
    uri = APIURL_TEMPLATE.format(TEST_CONFIG["longitude"], TEST_CONFIG["latitude"])
    aioclient_mock.get(uri, text=api_response)
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert not state
