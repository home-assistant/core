"""Fixtures for the Trafikverket Weatherstation integration."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime
from unittest.mock import patch

import pytest
from pytrafikverket import WeatherStationInfoModel

from homeassistant.components.trafikverket_weatherstation.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture
async def load_int(
    hass: HomeAssistant, mock_response: WeatherStationInfoModel
) -> MockConfigEntry:
    """Set up the Trafikverket Weatherstation integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=ENTRY_CONFIG,
    )

    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


@pytest.fixture(name="mock_response")
async def mock_weather_response(
    get_data: WeatherStationInfoModel,
) -> AsyncGenerator[None]:
    """Mock a successful response."""
    with patch(
        "homeassistant.components.trafikverket_weatherstation.coordinator.TrafikverketWeather.async_get_weather",
        return_value=get_data,
    ):
        yield


@pytest.fixture(name="get_data")
async def get_data_from_library(hass: HomeAssistant) -> WeatherStationInfoModel:
    """Retrieve data from Trafikverket Weatherstation library."""
    return WeatherStationInfoModel(
        station_name="Arlanda",
        station_id="227",
        road_temp=-3.4,
        air_temp=-3.0,
        dew_point=-5.0,
        humidity=84.1,
        visible_distance=20000.0,
        precipitationtype="no",
        raining=False,
        snowing=False,
        road_ice=None,
        road_ice_depth=None,
        road_snow=None,
        road_snow_depth=None,
        road_water=None,
        road_water_depth=None,
        road_water_equivalent_depth=None,
        winddirection="202",
        wind_height=6.0,
        windforce=1.2,
        windforcemax=2.3,
        measure_time=datetime.fromisoformat("2024-12-30T23:00:03+01:00"),
        precipitation_amount=0.0,
        modified_time=datetime.fromisoformat("2024-12-30T22:03:45.143000+00:00"),
    )
