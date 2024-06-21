"""Tests for the Tankerkoening integration."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from aiotankerkoenig.exceptions import (
    TankerkoenigConnectionError,
    TankerkoenigError,
    TankerkoenigInvalidKeyError,
    TankerkoenigRateLimitError,
)
import pytest

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
import homeassistant.util.dt as dt_util

from .const import CONFIG_DATA

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("setup_integration")
async def test_rate_limit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tankerkoenig: AsyncMock,
    caplog: pytest.LogCaptureFixture,
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
    assert (
        "API rate limit reached, consider to increase polling interval" in caplog.text
    )
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
            "API rate limit reached, consider to increase polling interval",
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
