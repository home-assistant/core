"""Test init of Airly integration."""
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_PLATFORM
from homeassistant.components.airly import set_update_interval
from homeassistant.components.airly.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import utcnow

from . import API_POINT_URL, init_integration

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_async_setup_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a successful setup entry."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("sensor.home_pm2_5")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "4.37"


async def test_config_not_ready(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_without_unique_id(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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

    aioclient_mock.get(API_POINT_URL, text=load_fixture("valid_station.json", "airly"))
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == "123-456"


async def test_config_with_turned_off_station(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
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

    aioclient_mock.get(API_POINT_URL, text=load_fixture("no_station.json", "airly"))
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_interval(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test correct update interval when the number of configured instances changes."""
    REMAINING_REQUESTS = 15
    HEADERS = {
        "X-RateLimit-Limit-day": "100",
        "X-RateLimit-Remaining-day": str(REMAINING_REQUESTS),
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
        text=load_fixture("valid_station.json", "airly"),
        headers=HEADERS,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    instances = 1

    assert aioclient_mock.call_count == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    update_interval = set_update_interval(instances, REMAINING_REQUESTS)
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
            text=load_fixture("valid_station.json", "airly"),
            headers=HEADERS,
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        instances = 2

        assert aioclient_mock.call_count == 3
        assert len(hass.config_entries.async_entries(DOMAIN)) == 2
        assert entry.state is ConfigEntryState.LOADED

        update_interval = set_update_interval(instances, REMAINING_REQUESTS)
        future = utcnow() + update_interval
        mock_utcnow.return_value = future
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        # call_count should increase by two because we have two instances configured
        assert aioclient_mock.call_count == 5


async def test_unload_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass, aioclient_mock)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


@pytest.mark.parametrize("old_identifier", ((DOMAIN, 123, 456), (DOMAIN, "123", "456")))
async def test_migrate_device_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    old_identifier: tuple[str, Any, Any],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device_info identifiers migration."""
    config_entry = MockConfigEntry(
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

    aioclient_mock.get(API_POINT_URL, text=load_fixture("valid_station.json", "airly"))
    config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={old_identifier}
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    migrated_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "123-456")}
    )
    assert device_entry.id == migrated_device_entry.id


async def test_remove_air_quality_entities(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test remove air_quality entities from registry."""
    registry = er.async_get(hass)

    registry.async_get_or_create(
        AIR_QUALITY_PLATFORM,
        DOMAIN,
        "123-456",
        suggested_object_id="home",
        disabled_by=None,
    )

    await init_integration(hass, aioclient_mock)

    entry = registry.async_get("air_quality.home")
    assert entry is None
