"""Tests for the Met Office diagnostics."""

import datetime as dt
import json

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_json_object_fixture
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
import requests_mock
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.metoffice.const import DOMAIN
from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.mark.freeze_time(dt.datetime(2024, 11, 23, 12, tzinfo=dt.UTC))
@pytest.mark.parametrize(
    "fetch_twice_daily",
    [
        pytest.param(False, id="twice_daily_not_fetched"),
        pytest.param(True, id="twice_daily_fetched"),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    requests_mock: requests_mock.Mocker,
    entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    fetch_twice_daily: bool,
) -> None:
    """Test diagnostics."""
    mock_json = await async_load_json_object_fixture(hass, "metoffice.json", DOMAIN)
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/hourly",
        text=json.dumps(mock_json["wavertree_hourly"]),
    )
    requests_mock.get(
        "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point/daily",
        text=json.dumps(mock_json["wavertree_daily"]),
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    if fetch_twice_daily:
        # The twice daily forecast is only fetched when it is requested
        await hass.services.async_call(
            WEATHER_DOMAIN,
            SERVICE_GET_FORECASTS,
            {"entity_id": "weather.met_office_wavertree", "type": "twice_daily"},
            blocking=True,
            return_response=True,
        )

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
