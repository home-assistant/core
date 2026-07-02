"""Fixtures for Swiss Hydrological Data integration tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.swiss_hydrological_data.const import CONF_STATION, DOMAIN

from tests.common import MockConfigEntry

STATION_ID = 2289

STATION_DATA = {
    "id": STATION_ID,
    "name": "Bern",
    "water-body-name": "Aare",
    "water-body-type": "river",
    "parameters": {
        "temperature": {
            "datetime": "2023-01-01T12:00:00",
            "unit": "°C",
            "value": 5.2,
            "max-24h": 6.1,
            "mean-24h": 5.4,
            "min-24h": 4.8,
        },
        "level": {
            "datetime": "2023-01-01T12:00:00",
            "unit": "m ü.M.",
            "value": 490.52,
            "max-24h": 491.02,
            "mean-24h": 490.62,
            "min-24h": 490.12,
        },
        "discharge": {
            "datetime": "2023-01-01T12:00:00",
            "unit": "m3/s",
            "value": 125.4,
            "max-24h": 135.2,
            "mean-24h": 128.3,
            "min-24h": 120.1,
        },
    },
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Aare Bern",
        data={CONF_STATION: STATION_ID},
        unique_id=str(STATION_ID),
    )


@pytest.fixture
def mock_swiss_hydro_data() -> Generator[MagicMock]:
    """Mock SwissHydroData."""
    with (
        patch(
            "homeassistant.components.swiss_hydrological_data.sensor.SwissHydroData",
        ) as mock_class,
        patch(
            "homeassistant.components.swiss_hydrological_data.config_flow.SwissHydroData",
            new=mock_class,
        ),
    ):
        mock_instance = mock_class.return_value
        mock_instance.get_station.return_value = STATION_DATA
        yield mock_instance


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Mock setup entry."""
    with patch(
        "homeassistant.components.swiss_hydrological_data.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
