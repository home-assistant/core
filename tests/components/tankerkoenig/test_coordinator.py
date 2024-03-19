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

from homeassistant.components.tankerkoenig.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("setup_integration")
async def test_rate_limit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tankerkoenig: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test detection of API rate limit."""
    assert config_entry.state == ConfigEntryState.LOADED
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
