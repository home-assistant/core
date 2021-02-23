"""Tests for the AEMET OpenData integration."""

import requests_mock

from homeassistant.components.aemet import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


def aemet_requests_mock(mock):
    """Mock requests performed to AEMET OpenData API."""

    station_3195_fixture = "aemet/station-3195.json"
    station_3195_data_fixture = "aemet/station-3195-data.json"
    station_list_fixture = "aemet/station-list.json"
    station_list_data_fixture = "aemet/station-list-data.json"

    town_28065_forecast_daily_fixture = "aemet/town-28065-forecast-daily.json"
    town_28065_forecast_daily_data_fixture = "aemet/town-28065-forecast-daily-data.json"
    town_28065_forecast_hourly_fixture = "aemet/town-28065-forecast-hourly.json"
    town_28065_forecast_hourly_data_fixture = (
        "aemet/town-28065-forecast-hourly-data.json"
    )
    town_id28065_fixture = "aemet/town-id28065.json"
    town_list_fixture = "aemet/town-list.json"

    mock.get(
        "https://opendata.aemet.es/opendata/api/observacion/convencional/datos/estacion/3195",
        text=load_fixture(station_3195_fixture),
    )
    mock.get(
        "https://opendata.aemet.es/opendata/sh/208c3ca3",
        text=load_fixture(station_3195_data_fixture),
    )
    mock.get(
        "https://opendata.aemet.es/opendata/api/observacion/convencional/todas",
        text=load_fixture(station_list_fixture),
    )
    mock.get(
        "https://opendata.aemet.es/opendata/sh/2c55192f",
        text=load_fixture(station_list_data_fixture),
    )
    mock.get(
        "https://opendata.aemet.es/opendata/api/prediccion/especifica/municipio/diaria/28065",
        text=load_fixture(town_28065_forecast_daily_fixture),
    )
    mock.get(
        "https://opendata.aemet.es/opendata/sh/64e29abb",
        text=load_fixture(town_28065_forecast_daily_data_fixture),
    )
    mock.get(
        "https://opendata.aemet.es/opendata/api/prediccion/especifica/municipio/horaria/28065",
        text=load_fixture(town_28065_forecast_hourly_fixture),
    )
    mock.get(
        "https://opendata.aemet.es/opendata/sh/18ca1886",
        text=load_fixture(town_28065_forecast_hourly_data_fixture),
    )
    mock.get(
        "https://opendata.aemet.es/opendata/api/maestro/municipio/id28065",
        text=load_fixture(town_id28065_fixture),
    )
    mock.get(
        "https://opendata.aemet.es/opendata/api/maestro/municipios",
        text=load_fixture(town_list_fixture),
    )


async def async_init_integration(
    hass: HomeAssistant,
    skip_setup: bool = False,
):
    """Set up the AEMET OpenData integration in Home Assistant."""

    with requests_mock.mock() as _m:
        aemet_requests_mock(_m)

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_API_KEY: "mock",
                CONF_LATITUDE: "40.30403754",
                CONF_LONGITUDE: "-3.72935236",
                CONF_NAME: "AEMET",
            },
        )
        entry.add_to_hass(hass)

        if not skip_setup:
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
