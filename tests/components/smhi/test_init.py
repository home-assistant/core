"""Test SMHI component setup process."""

from pysmhi.const import API_POINT_FORECAST

from homeassistant.components.smhi.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import ENTITY_ID, TEST_CONFIG, TEST_CONFIG_MIGRATE

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, api_response: str
) -> None:
    """Test setup entry."""
    uri = API_POINT_FORECAST.format(
        TEST_CONFIG["location"]["longitude"], TEST_CONFIG["location"]["latitude"]
    )
    aioclient_mock.get(uri, text=api_response)
    entry = MockConfigEntry(domain=DOMAIN, title="test", data=TEST_CONFIG, version=3)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state


async def test_remove_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, api_response: str
) -> None:
    """Test remove entry."""
    uri = API_POINT_FORECAST.format(
        TEST_CONFIG["location"]["longitude"], TEST_CONFIG["location"]["latitude"]
    )
    aioclient_mock.get(uri, text=api_response)
    entry = MockConfigEntry(domain=DOMAIN, title="test", data=TEST_CONFIG, version=3)
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
    uri = API_POINT_FORECAST.format(
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
        unique_id="59.32624, 17.84197",
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state

    assert entry.version == 3
    assert entry.unique_id == "59.32624-17.84197"
    assert entry.data == TEST_CONFIG

    entity_get = entity_registry.async_get(entity.entity_id)
    assert entity_get.unique_id == "59.32624, 17.84197"


async def test_migrate_from_future_version(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, api_response: str
) -> None:
    """Test migrate entry not possible from future version."""
    uri = API_POINT_FORECAST.format(
        TEST_CONFIG_MIGRATE["longitude"], TEST_CONFIG_MIGRATE["latitude"]
    )
    aioclient_mock.get(uri, text=api_response)
    entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG_MIGRATE, version=4)
    entry.add_to_hass(hass)
    assert entry.version == 4

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.MIGRATION_ERROR
