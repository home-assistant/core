"""Fixtures for the Open-Meteo integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from open_meteo import AirQuality, Forecast
import pytest

from homeassistant.components.open_meteo.const import DOMAIN
from homeassistant.const import CONF_ZONE

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Home",
        domain=DOMAIN,
        data={CONF_ZONE: "zone.home"},
        unique_id="zone.home",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.open_meteo.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_open_meteo(request: pytest.FixtureRequest) -> Generator[MagicMock]:
    """Return a mocked Open-Meteo client."""
    forecast_fixture: str = "forecast.json"
    air_quality_fixture: str = "air_quality.json"

    forecast = Forecast.from_json(load_fixture(forecast_fixture, DOMAIN))
    air_quality = AirQuality.from_json(load_fixture(air_quality_fixture, DOMAIN))
    with patch(
        "homeassistant.components.open_meteo.coordinator.OpenMeteo", autospec=True
    ) as open_meteo_mock:
        open_meteo = open_meteo_mock.return_value
        open_meteo.forecast.return_value = forecast
        open_meteo.air_quality.return_value = air_quality
        yield open_meteo
