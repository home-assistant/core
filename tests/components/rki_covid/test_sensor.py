"""Test the RKI Covide numbers integration sensor."""
from unittest.mock import AsyncMock, patch

from tests.test_util.aiohttp import AiohttpClientMocker
from homeassistant.components.rki_covid.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from homeassistant.components.rki_covid.coordinator import RkiCovidDataUpdateCoordinator
from rki_covid_parser.parser import RkiCovidParser
from rki_covid_parser.const import (
    DISTRICTS_URL,
    DISTRICTS_URL_RECOVERED,
    DISTRICTS_URL_NEW_CASES,
    DISTRICTS_URL_NEW_RECOVERED,
    DISTRICTS_URL_NEW_DEATHS,
    HOSPITALIZATION_URL,
    VACCINATIONS_URL,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from aiohttp import ClientError
from tests.components.rki_covid import MOCK_DISTRICTS, MOCK_STATES, MOCK_COUNTRY


async def test_sensor_with_district(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test sensor when data coordinator could not be initialized."""
    coordinator = RkiCovidDataUpdateCoordinator(hass)
    coordinator.parser = RkiCovidParser(async_get_clientsession(hass))
    coordinator.parser.load_data = AsyncMock(return_value=None)
    coordinator.parser.districts = MOCK_DISTRICTS
    coordinator.parser.states = MOCK_STATES
    coordinator.parser.country = MOCK_COUNTRY
    with patch(
        "homeassistant.components.rki_covid.coordinator.RkiCovidDataUpdateCoordinator",
        return_value=coordinator,
    ):
        entry = MockConfigEntry(domain=DOMAIN, data={"county": "SK Amberg"})
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get("sensor.sk_amberg_count").state == "1337"
        assert entry.unique_id == "SK Amberg"


async def test_sensor_with_state(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test sensor setup with mock data."""
    coordinator = RkiCovidDataUpdateCoordinator(hass)
    coordinator.parser = RkiCovidParser(async_get_clientsession(hass))
    coordinator.parser.load_data = AsyncMock(return_value=None)
    coordinator.parser.districts = MOCK_DISTRICTS
    coordinator.parser.states = MOCK_STATES
    coordinator.parser.country = MOCK_COUNTRY
    with patch(
        "homeassistant.components.rki_covid.coordinator.RkiCovidDataUpdateCoordinator",
        return_value=coordinator,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="test entry",
            unique_id="0123456",
            data={"county": "SK Amberg"},
        )
        entry.add_to_hass(hass)
        entity_id = "sensor.sk_amberg_count"
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state

        assert hass.states.get("sensor.sk_amberg_count") is not None
        assert hass.states.get("sensor.sk_amberg_count").state == "1337"
        assert entry.unique_id == "SK Amberg"


async def test_async_setup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


async def test_sensor_with_invalid_config_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test sensor with an invalid config entry should fail with exception."""
    aioclient_mock.get(DISTRICTS_URL, exc=ClientError)
    aioclient_mock.get(DISTRICTS_URL_RECOVERED, exc=ClientError)
    aioclient_mock.get(DISTRICTS_URL_NEW_CASES, exc=ClientError)
    aioclient_mock.get(DISTRICTS_URL_NEW_RECOVERED, exc=ClientError)
    aioclient_mock.get(DISTRICTS_URL_NEW_DEATHS, exc=ClientError)
    aioclient_mock.get(HOSPITALIZATION_URL, exc=ClientError)
    aioclient_mock.get(VACCINATIONS_URL, exc=ClientError)

    entry = MockConfigEntry(domain=DOMAIN, data={"county": "SK Invalid"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
