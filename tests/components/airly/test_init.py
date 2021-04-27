"""Test init of Airly integration."""
from unittest.mock import patch

from homeassistant.components.airly import set_update_interval
from homeassistant.components.airly.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.util.dt import utcnow

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
    REMAINING_RQUESTS = 15
    HEADERS = {
        "X-RateLimit-Limit-day": "100",
        "X-RateLimit-Remaining-day": str(REMAINING_RQUESTS),
    }

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
    instances = 1

    assert aioclient_mock.call_count == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    update_interval = set_update_interval(instances, REMAINING_RQUESTS)
    future = utcnow() + update_interval
    with patch("homeassistant.util.dt.utcnow") as mock_utcnow:
        mock_utcnow.return_value = future
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        # call_count should increase by one because we have one instance configured
        assert aioclient_mock.call_count == 2

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
        instances = 2

        assert aioclient_mock.call_count == 3
        assert len(hass.config_entries.async_entries(DOMAIN)) == 2
        assert entry.state == ENTRY_STATE_LOADED

        update_interval = set_update_interval(instances, REMAINING_RQUESTS)
        future = utcnow() + update_interval
        mock_utcnow.return_value = future
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        # call_count should increase by two because we have two instances configured
        assert aioclient_mock.call_count == 5


async def test_unload_entry(hass, aioclient_mock):
    """Test successful unload of entry."""
    entry = await init_integration(hass, aioclient_mock)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)
