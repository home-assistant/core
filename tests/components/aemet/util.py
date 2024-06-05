"""Tests for the AEMET OpenData integration."""

from typing import Any
from unittest.mock import patch

from aemet_opendata.const import ATTR_DATA

from homeassistant.components.aemet.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_value_fixture

FORECAST_DAILY_DATA_MOCK = {
    ATTR_DATA: load_json_value_fixture("aemet/town-28065-forecast-daily-data.json"),
}

FORECAST_HOURLY_DATA_MOCK = {
    ATTR_DATA: load_json_value_fixture("aemet/town-28065-forecast-hourly-data.json"),
}

STATION_DATA_MOCK = {
    ATTR_DATA: load_json_value_fixture("aemet/station-3195-data.json"),
}

STATIONS_DATA_MOCK = {
    ATTR_DATA: load_json_value_fixture("aemet/station-list-data.json"),
}

TOWN_DATA_MOCK = {
    ATTR_DATA: load_json_value_fixture("aemet/town-id28065.json"),
}

TOWNS_DATA_MOCK = {
    ATTR_DATA: load_json_value_fixture("aemet/town-list.json"),
}


def mock_api_call(cmd: str, fetch_data: bool = False) -> dict[str, Any]:
    """Mock AEMET OpenData API calls."""
    if cmd == "maestro/municipio/id28065":
        return TOWN_DATA_MOCK
    if cmd == "maestro/municipios":
        return TOWNS_DATA_MOCK
    if (
        cmd
        == "observacion/convencional/datos/estacion/3195"  # codespell:ignore convencional
    ):
        return STATION_DATA_MOCK
    if cmd == "observacion/convencional/todas":  # codespell:ignore convencional
        return STATIONS_DATA_MOCK
    if cmd == "prediccion/especifica/municipio/diaria/28065":
        return FORECAST_DAILY_DATA_MOCK
    if cmd == "prediccion/especifica/municipio/horaria/28065":
        return FORECAST_HOURLY_DATA_MOCK
    return {}


async def async_init_integration(hass: HomeAssistant):
    """Set up the AEMET OpenData integration in Home Assistant."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "api-key",
            CONF_LATITUDE: "40.30403754",
            CONF_LONGITUDE: "-3.72935236",
            CONF_NAME: "AEMET",
        },
        entry_id="7442b231f139e813fc1939281123f220",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.aemet.AEMET.api_call",
        side_effect=mock_api_call,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
