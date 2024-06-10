"""Test SMHI component setup process."""

from unittest.mock import patch

from smhi.smhi_lib import APIURL_TEMPLATE

from homeassistant.components.smhi.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import ENTITY_ID, TEST_CONFIG, TEST_CONFIG_MIGRATE

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, api_response: str
) -> None:
    """Test setup entry."""
    uri = APIURL_TEMPLATE.format(
        TEST_CONFIG["location"]["longitude"], TEST_CONFIG["location"]["latitude"]
    )
    aioclient_mock.get(uri, text=api_response)
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG, version=2)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state


async def test_remove_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, api_response: str
) -> None:
    """Test remove entry."""
    uri = APIURL_TEMPLATE.format(
        TEST_CONFIG["location"]["longitude"], TEST_CONFIG["location"]["latitude"]
    )
    aioclient_mock.get(uri, text=api_response)
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG, version=2)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert not state


async def test_migrate_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    api_response: str,
) -> None:
    """Test migrate entry data."""
    uri = APIURL_TEMPLATE.format(
        TEST_CONFIG_MIGRATE["longitude"], TEST_CONFIG_MIGRATE["latitude"]
    )
    aioclient_mock.get(uri, text=api_response)
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG_MIGRATE)
    entry.add_to_hass(hass)
    assert entry.version == 1

    entity = entity_registry.async_get_or_create(
        domain="weather",
        config_entry=entry,
        original_name="Weather",
        platform="smhi",
        supported_features=0,
        unique_id="17.84197, 17.84197",
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state

    assert entry.version == 2
    assert entry.unique_id == "17.84197-17.84197"

    entity_get = entity_registry.async_get(entity.entity_id)
    assert entity_get.unique_id == "17.84197, 17.84197"


async def test_migrate_entry_failed(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, api_response: str
) -> None:
    """Test migrate entry data that fails."""
    uri = APIURL_TEMPLATE.format(
        TEST_CONFIG_MIGRATE["longitude"], TEST_CONFIG_MIGRATE["latitude"]
    )
    aioclient_mock.get(uri, text=api_response)
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG_MIGRATE)
    entry.add_to_hass(hass)
    assert entry.version == 1

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_update_entry",
        return_value=False,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.version == 1
