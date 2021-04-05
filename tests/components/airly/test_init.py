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

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture
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
    HEADERS = {"X-RateLimit-Limit-day": "100", "X-RateLimit-Remaining-day": "15"}
    POINT = datetime(
        year=2030, month=3, day=2, hour=21, minute=20, second=0, tzinfo=NATIVE_UTC
    )

    with patch("homeassistant.components.airly.dt_util.utcnow", return_value=POINT):
        async_fire_time_changed(hass, POINT)
        await hass.async_block_till_done()

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

        aioclient_mock.get(
            API_POINT_URL,
            text=load_fixture("airly_valid_station.json"),
            headers=HEADERS,
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert aioclient_mock.call_count == 1
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        assert entry.state == ENTRY_STATE_LOADED

        # We have 160 minutes to midnight, 15 remaining requests and one instance so
        # next update will be after ceil(160 / 15 * 1) = 11 minutes
        future = POINT + timedelta(minutes=11)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        assert aioclient_mock.call_count == 2

        # We have 160 minutes to midnight, 15 remaining requests and one instance so
        # next update will be after ceil(160 / 15 * 1) = 11 minutes
        future = future + timedelta(minutes=11)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        assert aioclient_mock.call_count == 3

        # Now we add the second Airly instance
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

        aioclient_mock.get(
            "https://airapi.airly.eu/v2/measurements/point?lat=66.660000&lng=111.110000",
            text=load_fixture("airly_valid_station.json"),
            headers=HEADERS,
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert aioclient_mock.call_count == 4
        assert len(hass.config_entries.async_entries(DOMAIN)) == 2
        assert entry.state == ENTRY_STATE_LOADED

        # We have 160 minutes to midnight, 15 remaining requests and two instances so
        # next update will be after ceil(160 / 15 * 2) = 22 minutes
        future = future + timedelta(minutes=22)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        # Both instances should be updated so call_count will increase by 2
        assert aioclient_mock.call_count == 6


async def test_unload_entry(hass, aioclient_mock):
    """Test successful unload of entry."""
    entry = await init_integration(hass, aioclient_mock)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)
