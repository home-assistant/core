"""Test SMHI component setup process."""
from smhi.smhi_lib import APIURL_TEMPLATE

from homeassistant.components.smhi.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import ENTITY_ID, TEST_CONFIG

from tests.common import MockConfigEntry, mock_registry
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


async def test_migrate_entities(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, api_response: str
) -> None:
    """Test migrate unique id."""
    uri = APIURL_TEMPLATE.format(TEST_CONFIG["longitude"], TEST_CONFIG["latitude"])
    aioclient_mock.get(uri, text=api_response)
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG, entry_id="12345")
    entry.add_to_hass(hass)

    mock_registry(
        hass,
        {
            "weather.smhi_test": er.RegistryEntry(
                entity_id="weather.smhi_test",
                unique_id="59.32624, 17.84197",
                platform="smhi",
                config_entry_id=entry.entry_id,
            ),
        },
    )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)

    weather_home = ent_reg.async_get("weather.smhi_test")
    assert weather_home.unique_id == "12345, 59.32624, 17.84197"


async def test_migrate_entities_completed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, api_response: str
) -> None:
    """Test migrate unique id."""
    uri = APIURL_TEMPLATE.format(TEST_CONFIG["longitude"], TEST_CONFIG["latitude"])
    aioclient_mock.get(uri, text=api_response)
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG, entry_id="12345")
    entry.add_to_hass(hass)

    mock_registry(
        hass,
        {
            "weather.smhi_test": er.RegistryEntry(
                entity_id="weather.smhi_test",
                unique_id="12345, 59.32624, 17.84197",
                platform="smhi",
                config_entry_id=entry.entry_id,
            ),
        },
    )

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)

    weather_home = ent_reg.async_get("weather.smhi_test")
    assert weather_home.unique_id == "12345, 59.32624, 17.84197"
