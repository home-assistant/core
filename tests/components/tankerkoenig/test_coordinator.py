"""Tests for the Tankerkoening integration."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

from aiotankerkoenig.exceptions import (
    TankerkoenigConnectionError,
    TankerkoenigError,
    TankerkoenigInvalidKeyError,
    TankerkoenigRateLimitError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.tankerkoenig.const import (
    CONF_STATIONS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ID, CONF_SHOW_ON_MAP, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .const import CONFIG_DATA, STATION


@pytest.mark.usefixtures("setup_integration")
async def test_rate_limit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tankerkoenig: AsyncMock,
) -> None:
    """Test detection of API rate limit."""
    assert config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get("binary_sensor.station_somewhere_street_1_status")
    assert state
    assert state.state == "on"

    tankerkoenig.prices.side_effect = TankerkoenigRateLimitError
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(minutes=DEFAULT_SCAN_INTERVAL)
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.station_somewhere_street_1_status")
    assert state
    assert state.state == STATE_UNAVAILABLE

    tankerkoenig.prices.side_effect = None
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(minutes=DEFAULT_SCAN_INTERVAL * 2)
    )
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.station_somewhere_street_1_status")
    assert state
    assert state.state == "on"


@pytest.mark.parametrize(
    ("exception", "expected_log"),
    [
        (
            TankerkoenigInvalidKeyError,
            "invalid key error occur during update of stations",
        ),
        (
            TankerkoenigRateLimitError,
            "You have reached the rate limit for the Tankerkoenig API",
        ),
        (TankerkoenigConnectionError, "error occur during update of stations"),
        (TankerkoenigError, "error occur during update of stations"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_update_exception_logging(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tankerkoenig: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    exception: None,
    expected_log: str,
) -> None:
    """Test log messages about exceptions during update."""
    tankerkoenig.prices.side_effect = exception
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(minutes=DEFAULT_SCAN_INTERVAL)
    )
    await hass.async_block_till_done()
    assert expected_log in caplog.text
    state = hass.states.get("binary_sensor.station_somewhere_street_1_status")
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("exception", "expected_log"),
    [
        (
            TankerkoenigInvalidKeyError,
            "invalid key error occur during setup of station",
        ),
        (TankerkoenigConnectionError, "connection error occur during setup of station"),
        (TankerkoenigError, "Error when adding station"),
    ],
)
async def test_setup_exception_logging(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tankerkoenig: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    exception: None,
    expected_log: str,
) -> None:
    """Test log messages about exceptions during setup."""
    config_entry.add_to_hass(hass)
    tankerkoenig.station_details.side_effect = exception

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert expected_log in caplog.text


async def test_automatic_registry_cleanup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tankerkoenig: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test automatic registry cleanup for obsolete entity and devices entries."""
    # setup normal
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert (
        len(er.async_entries_for_config_entry(entity_registry, config_entry.entry_id))
        == 4
    )
    assert (
        len(dr.async_entries_for_config_entry(device_registry, config_entry.entry_id))
        == 1
    )

    # add obsolete entity and device entries
    obsolete_station_id = "aabbccddee-xxxx-xxxx-xxxx-ff11223344"

    entity_registry.async_get_or_create(
        DOMAIN,
        BINARY_SENSOR_DOMAIN,
        f"{obsolete_station_id}_status",
        config_entry=config_entry,
    )
    entity_registry.async_get_or_create(
        DOMAIN,
        SENSOR_DOMAIN,
        f"{obsolete_station_id}_e10",
        config_entry=config_entry,
    )
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(ATTR_ID, obsolete_station_id)},
        name="Obsolete Station",
    )

    assert (
        len(er.async_entries_for_config_entry(entity_registry, config_entry.entry_id))
        == 6
    )
    assert (
        len(dr.async_entries_for_config_entry(device_registry, config_entry.entry_id))
        == 2
    )

    # reload config entry to trigger automatic cleanup
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        len(er.async_entries_for_config_entry(entity_registry, config_entry.entry_id))
        == 4
    )
    assert (
        len(dr.async_entries_for_config_entry(device_registry, config_entry.entry_id))
        == 1
    )


async def test_many_stations_warning(
    hass: HomeAssistant, tankerkoenig: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the warning about morethan 10 selected stations."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            **CONFIG_DATA,
            CONF_STATIONS: [
                "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8",
                "36b4b812-xxxx-xxxx-xxxx-c51735325858",
                "54e2b642-xxxx-xxxx-xxxx-87cd4e9867f1",
                "11b5c130-xxxx-xxxx-xxxx-856b8489b528",
                "a9137924-xxxx-xxxx-xxxx-7029d7eb073f",
                "57c6d275-xxxx-xxxx-xxxx-7f6ad9e6d638",
                "bbc3c3a2-xxxx-xxxx-xxxx-840cc3d496b6",
                "1db63dd9-xxxx-xxxx-xxxx-a889b53cbc65",
                "18d7262e-xxxx-xxxx-xxxx-4a61ad302e14",
                "a8041aa3-xxxx-xxxx-xxxx-7c6b180e5a40",
                "739aa0eb-xxxx-xxxx-xxxx-a3d7b6c8a42f",
                "9ad9fb26-xxxx-xxxx-xxxx-84e6a02b3096",
                "74267867-xxxx-xxxx-xxxx-74ce3d45882c",
                "86657222-xxxx-xxxx-xxxx-a2b795ab3cf9",
            ],
        },
        options={CONF_SHOW_ON_MAP: True},
        unique_id="51.0_13.0",
    )
    mock_config.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert "Found more than 10 stations to check" in caplog.text


async def test_station_details_cached(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tankerkoenig: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test station details are only fetched again after the cache expired."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert tankerkoenig.station_details.call_count == 1

    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert tankerkoenig.station_details.call_count == 1
    assert hass.states.get("binary_sensor.station_somewhere_street_1_status")
    # The cached fuel fields still create the price sensors
    for entity_id in (
        "sensor.station_somewhere_street_1_super_e10",
        "sensor.station_somewhere_street_1_super",
        "sensor.station_somewhere_street_1_diesel",
    ):
        state = hass.states.get(entity_id)
        assert state
        assert state.state != STATE_UNAVAILABLE

    freezer.tick(timedelta(days=8))
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert tankerkoenig.station_details.call_count == 2


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(TankerkoenigConnectionError, id="connection_error"),
        pytest.param(TankerkoenigRateLimitError, id="rate_limit"),
    ],
)
async def test_expired_cache_used_when_details_fail(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tankerkoenig: AsyncMock,
    freezer: FrozenDateTimeFactory,
    exception: type[Exception],
) -> None:
    """Test expired station details are used when they cannot be fetched."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(days=8))
    tankerkoenig.station_details.side_effect = exception
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert tankerkoenig.station_details.call_count == 2
    assert hass.states.get("binary_sensor.station_somewhere_street_1_status")


@pytest.mark.usefixtures("tankerkoenig")
async def test_station_cache_removed_with_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test the station cache is removed together with the config entry."""
    key = f"{DOMAIN}.{config_entry.entry_id}.stations"
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert key in hass_storage

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert key not in hass_storage


async def test_fetched_stations_saved_when_setup_fails(
    hass: HomeAssistant,
    tankerkoenig: AsyncMock,
    hass_storage: dict[str, Any],
) -> None:
    """Test stations fetched before a failing one are kept in the cache."""
    first, second = (
        "3bcd61da-xxxx-xxxx-xxxx-19d5523a7ae8",
        "36b4b812-xxxx-xxxx-xxxx-c51735325858",
    )
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_SHOW_ON_MAP: True},
        data={**CONFIG_DATA, CONF_STATIONS: [first, second]},
    )
    tankerkoenig.station_details.side_effect = [
        STATION,
        TankerkoenigConnectionError,
    ]
    config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    stations = hass_storage[f"{DOMAIN}.{config_entry.entry_id}.stations"]["data"][
        "stations"
    ]
    assert list(stations) == [first]
