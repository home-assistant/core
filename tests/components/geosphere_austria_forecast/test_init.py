"""Test the GeoSphere Austria Forecast integration setup."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, call

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_fire_time_changed_exact,
)
from zamg import NwpForecast, ZamgApiError, ZamgNoDataError

from homeassistant.components.geosphere_austria_forecast.const import DOMAIN
from homeassistant.components.geosphere_austria_forecast.coordinator import (
    SECONDS_PER_REQUEST_SLOT,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import init_integration


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nwp_client: MagicMock,
) -> None:
    """Test the entry loads and unloads."""
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_nwp_client.request_timeout == 60

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ZamgApiError("Server error", status_code=500), id="api_error"),
        pytest.param(ZamgNoDataError("Invalid data"), id="no_data"),
    ],
)
async def test_setup_retries_on_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nwp_client: MagicMock,
    exception: Exception,
) -> None:
    """Test setup is retried when the forecast cannot be fetched."""
    mock_nwp_client.get_forecast.side_effect = exception
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_one_request_per_hour(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nwp_client: MagicMock,
) -> None:
    """Test the location is fetched with its coordinates once per hour."""
    await init_integration(hass, mock_config_entry)
    assert mock_nwp_client.get_forecast.await_args_list == [
        call(latitude=48.2877, longitude=15.98486)
    ]

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_nwp_client.get_forecast.await_count == 2


async def test_locations_share_the_request_limit(
    hass: HomeAssistant,
    mock_nwp_client: MagicMock,
    forecast: NwpForecast,
    six_locations: list[MockConfigEntry],
) -> None:
    """Test no more than five requests run at a time over all locations."""
    running = 0
    five_running = asyncio.Event()
    release = asyncio.Event()

    async def get_forecast(**kwargs: float) -> NwpForecast:
        nonlocal running
        running += 1
        if running == 5:
            five_running.set()
        await release.wait()
        running -= 1
        return forecast

    mock_nwp_client.get_forecast.side_effect = get_forecast
    setup = hass.async_create_task(async_setup_component(hass, DOMAIN, {}))
    await five_running.wait()
    # Give the sixth location the chance to start its request.
    for _ in range(20):
        await asyncio.sleep(0)
    assert running == 5

    release.set()
    assert await setup
    await hass.async_block_till_done()
    assert [entry.state for entry in six_locations] == [ConfigEntryState.LOADED] * 6
    assert mock_nwp_client.get_forecast.await_count == 6


@pytest.mark.parametrize("request_slot_seconds", [SECONDS_PER_REQUEST_SLOT])
@pytest.mark.usefixtures("six_locations")
async def test_request_slot_is_held_for_a_second(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_nwp_client: MagicMock,
    forecast: NwpForecast,
) -> None:
    """Test a sixth request waits until a second after the first five."""
    requests = 0
    requested = {5: asyncio.Event(), 6: asyncio.Event()}

    async def get_forecast(**kwargs: float) -> NwpForecast:
        nonlocal requests
        requests += 1
        if requests in requested:
            requested[requests].set()
        return forecast

    mock_nwp_client.get_forecast.side_effect = get_forecast
    setup = hass.async_create_task(async_setup_component(hass, DOMAIN, {}))
    await requested[5].wait()

    freezer.tick(timedelta(seconds=SECONDS_PER_REQUEST_SLOT - 0.1))
    async_fire_time_changed_exact(hass)
    # Give the sixth location the chance to start its request.
    for _ in range(20):
        await asyncio.sleep(0)
    assert requests == 5

    freezer.tick(timedelta(seconds=0.1))
    async_fire_time_changed_exact(hass)
    await requested[6].wait()

    freezer.tick(timedelta(seconds=SECONDS_PER_REQUEST_SLOT))
    async_fire_time_changed_exact(hass)
    assert await setup
    await hass.async_block_till_done()
