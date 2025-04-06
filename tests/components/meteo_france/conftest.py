"""Meteo-France generic test utils."""

from unittest.mock import patch

from meteofrance_api.model import CurrentPhenomenons, Forecast, Rain
import pytest

from homeassistant.components.meteo_france.const import CONF_CITY, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture(autouse=True)
def patch_requests():
    """Stub out services that makes requests."""
    with patch("homeassistant.components.meteo_france.MeteoFranceClient") as mock_data:
        mock_data = mock_data.return_value
        mock_data.get_forecast.return_value = Forecast(
            load_json_object_fixture("raw_forecast.json", DOMAIN)
        )
        mock_data.get_rain.return_value = Rain(
            load_json_object_fixture("raw_rain.json", DOMAIN)
        )
        mock_data.get_warning_current_phenomenons.return_value = CurrentPhenomenons(
            load_json_object_fixture("raw_warning_current_phenomenons.json", DOMAIN)
        )
        yield mock_data


@pytest.fixture(name="config_entry")
def get_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create and register mock config entry."""
    entry_data = {
        CONF_CITY: "La Clusaz",
        CONF_LATITUDE: 45.90417,
        CONF_LONGITUDE: 6.42306,
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        unique_id=f"{entry_data[CONF_LATITUDE], entry_data[CONF_LONGITUDE]}",
        title=entry_data[CONF_CITY],
        data=entry_data,
    )
    config_entry.add_to_hass(hass)
    return config_entry
