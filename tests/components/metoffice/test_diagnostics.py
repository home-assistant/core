"""Tests for the Met Office diagnostics."""

import datetime as dt

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def _setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the Met Office config entry."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.freeze_time(dt.datetime(2024, 11, 23, 12, tzinfo=dt.UTC))
@pytest.mark.usefixtures("wavertree_data")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics before the twice daily forecast is fetched."""
    await _setup_entry(hass, entry)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot


@pytest.mark.freeze_time(dt.datetime(2024, 11, 23, 12, tzinfo=dt.UTC))
@pytest.mark.usefixtures("wavertree_data")
async def test_diagnostics_twice_daily_fetched(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics after the twice daily forecast is fetched."""
    await _setup_entry(hass, entry)
    # The twice daily forecast is only fetched when it is requested
    await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": "weather.met_office_wavertree", "type": "twice_daily"},
        blocking=True,
        return_response=True,
    )

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
