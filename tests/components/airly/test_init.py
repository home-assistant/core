"""Test init of Airly integration."""
from datetime import datetime, timedelta
from unittest.mock import patch

from homeassistant.components.airly.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.util.dt import NATIVE_UTC

from . import API_POINT_URL

from tests.common import MockConfigEntry, load_fixture
from tests.components.airly import init_integration


async def test_async_setup_entry(hass, aioclient_mock):
    """Test a successful setup entry."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("air_quality.home")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "14"


async def test_config_not_ready(hass, aioclient_mock):
    """Test for setup failure if connection to Airly is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="123-456",
        data={
            "api_key": "foo",
            "latitude": 123,
            "longitude": 456,
            "name": "Home",
            "use_nearest": True,
        },
    )

    aioclient_mock.get(API_POINT_URL, exc=ConnectionError())
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_config_without_unique_id(hass, aioclient_mock):
    """Test for setup entry without unique_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        data={
            "api_key": "foo",
            "latitude": 123,
            "longitude": 456,
            "name": "Home",
        },
    )

    aioclient_mock.get(API_POINT_URL, text=load_fixture("airly_valid_station.json"))
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ENTRY_STATE_LOADED
    assert entry.unique_id == "123-456"


async def test_config_with_turned_off_station(hass, aioclient_mock):
    """Test for setup entry for a turned off measuring station."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="123-456",
        data={
            "api_key": "foo",
            "latitude": 123,
            "longitude": 456,
            "name": "Home",
        },
    )

    aioclient_mock.get(API_POINT_URL, text=load_fixture("airly_no_station.json"))
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_update_interval(hass, aioclient_mock):
    """Test correct update interval when the number of configured instances changes."""
    point = datetime(
        year=2020, month=3, day=2, hour=21, minute=21, second=0, tzinfo=NATIVE_UTC
    )
    with patch("homeassistant.core.dt_util.utcnow") as mock_utcnow:
        mock_utcnow.return_value = point

        entry = await init_integration(hass, aioclient_mock)

        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        assert entry.state == ENTRY_STATE_LOADED
        await hass.async_block_till_done()

        instance1 = list(hass.data[DOMAIN].values())[0]
        assert instance1.airly.requests_remaining == 11
        assert instance1.airly.requests_per_day == 100
        assert instance1.update_interval == timedelta(minutes=14)

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Work",
            unique_id="66.66-111.11",
            data={
                "api_key": "foo",
                "latitude": 66.66,
                "longitude": 111.11,
                "name": "Work",
            },
        )
        headers = {"X-RateLimit-Limit-day": "100", "X-RateLimit-Remaining-day": "10"}

        aioclient_mock.get(
            "https://airapi.airly.eu/v2/measurements/point?lat=66.660000&lng=111.110000",
            text=load_fixture("airly_valid_station.json"),
            headers=headers,
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.config_entries.async_entries(DOMAIN)) == 2
        assert entry.state == ENTRY_STATE_LOADED
        instance2 = list(hass.data[DOMAIN].values())[1]
        assert instance2.airly.requests_remaining == 10
        assert instance2.airly.requests_per_day == 100
        assert instance2.update_interval == timedelta(minutes=31)


async def test_unload_entry(hass, aioclient_mock):
    """Test successful unload of entry."""
    entry = await init_integration(hass, aioclient_mock)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)
