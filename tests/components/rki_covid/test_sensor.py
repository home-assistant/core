"""Test the RKI Covide numbers integration sensor."""
from tests.common import load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker
from homeassistant.components.rki_covid.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from tests.common import MockConfigEntry
from rki_covid_parser.const import (
    DISTRICTS_URL,
    DISTRICTS_URL_RECOVERED,
    DISTRICTS_URL_NEW_CASES,
    DISTRICTS_URL_NEW_RECOVERED,
    DISTRICTS_URL_NEW_DEATHS,
    HOSPITALIZATION_URL,
    VACCINATIONS_URL,
)
from aiohttp import ClientError


async def test_sensor_with_data(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test sensor when data coordinator could not be initialized."""
    aioclient_mock.get(
        DISTRICTS_URL, text=load_fixture("response_districts.json", "rki_covid")
    )
    aioclient_mock.get(
        DISTRICTS_URL_RECOVERED,
        text=load_fixture("response_recovered.json", "rki_covid"),
    )
    aioclient_mock.get(
        VACCINATIONS_URL,
        text=load_fixture("germany_vaccinations_by_state.tsv", "rki_covid"),
    )
    aioclient_mock.get(
        DISTRICTS_URL_NEW_CASES,
        text=load_fixture("response_new_cases.json", "rki_covid"),
    )
    aioclient_mock.get(
        DISTRICTS_URL_NEW_RECOVERED,
        text=load_fixture("response_new_recovered.json", "rki_covid"),
    )
    aioclient_mock.get(
        DISTRICTS_URL_NEW_DEATHS,
        text=load_fixture("response_new_death.json", "rki_covid"),
    )

    aioclient_mock.get(
        HOSPITALIZATION_URL,
        text=load_fixture("hospitalization.csv", "rki_covid"),
    )

    entry1 = MockConfigEntry(domain=DOMAIN, data={"county": "SK Amberg"})
    entry1.add_to_hass(hass)
    await hass.config_entries.async_setup(entry1.entry_id)
    await hass.async_block_till_done()

    entry2 = MockConfigEntry(domain=DOMAIN, data={"county": "BL Bayern"})
    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)
    await hass.async_block_till_done()

    entry3 = MockConfigEntry(domain=DOMAIN, data={"county": "Deutschland"})
    entry3.add_to_hass(hass)
    await hass.config_entries.async_setup(entry3.entry_id)
    await hass.async_block_till_done()

    # verify district
    amberg_count = hass.states.get("sensor.sk_amberg_count")
    assert amberg_count
    assert amberg_count.state == "1940"

    # verify state
    state_count = hass.states.get("sensor.bl_bayern_count")
    assert state_count
    assert state_count.state == "691474"

    # verify county
    county_count = hass.states.get("sensor.deutschland_count")
    assert county_count
    assert county_count.state == "4046112"


async def test_async_setup(
    hass: HomeAssistant,
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
