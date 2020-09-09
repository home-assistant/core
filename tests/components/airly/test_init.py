"""Test init of Airly integration."""
from datetime import timedelta
import json

from homeassistant.components.airly.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import STATE_UNAVAILABLE

from tests.async_mock import patch
from tests.common import MockConfigEntry, load_fixture
from tests.components.airly import init_integration


async def test_async_setup_entry(hass):
    """Test a successful setup entry."""
    await init_integration(hass)

    state = hass.states.get("air_quality.home")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "14"


async def test_config_not_ready(hass):
    """Test for setup failure if connection to Airly is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="55.55-122.12",
        data={
            "api_key": "foo",
            "latitude": 55.55,
            "longitude": 122.12,
            "name": "Home",
        },
    )

    with patch("airly._private._RequestsHandler.get", side_effect=ConnectionError()):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_config_without_unique_id(hass):
    """Test for setup entry without unique_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        data={
            "api_key": "foo",
            "latitude": 55.55,
            "longitude": 122.12,
            "name": "Home",
        },
    )

    with patch(
        "airly._private._RequestsHandler.get",
        return_value=json.loads(load_fixture("airly_valid_station.json")),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state == ENTRY_STATE_LOADED
        assert entry.unique_id == "55.55-122.12"


async def test_config_with_turned_off_station(hass):
    """Test for setup entry for a turned off measuring station."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="55.55-122.12",
        data={
            "api_key": "foo",
            "latitude": 55.55,
            "longitude": 122.12,
            "name": "Home",
        },
    )

    with patch(
        "airly._private._RequestsHandler.get",
        return_value=json.loads(load_fixture("airly_no_station.json")),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_update_interval(hass):
    """Test correct update interval when the number of configured instances changes."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED
    for instance in hass.data[DOMAIN].values():
        assert instance.update_interval == timedelta(minutes=15)

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

    with patch(
        "airly._private._RequestsHandler.get",
        return_value=json.loads(load_fixture("airly_valid_station.json")),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert entry.state == ENTRY_STATE_LOADED
    for instance in hass.data[DOMAIN].values():
        assert instance.update_interval == timedelta(minutes=30)


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)
