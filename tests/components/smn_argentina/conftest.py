"""Fixtures for SMN integration tests."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_location_data() -> dict:
    """Return mock location data from georef API."""
    return {
        "id": "4864",
        "name": "Ciudad de Buenos Aires",
        "department": "Comuna 1",
        "province": "Ciudad Autónoma de Buenos Aires",
        "coord": {"lat": -34.6217, "lon": -58.4258},
    }


@pytest.fixture
def mock_current_weather() -> dict:
    """Return mock current weather data."""
    return {
        "temperature": 22.5,
        "feels_like": 21.0,
        "humidity": 65,
        "pressure": 1013.2,
        "visibility": 10000,
        "weather": {"id": 3, "description": "Despejado"},
        "wind": {"speed": 15.5, "deg": 180},
        "location": {
            "id": "4864",
            "name": "Ciudad de Buenos Aires",
            "province": "Ciudad Autónoma de Buenos Aires",
        },
    }


@pytest.fixture
def mock_forecast_data() -> dict:
    """Return mock forecast data."""
    return {
        "updated": "2025-12-30T17:32:59-03:00",
        "location": {
            "id": 4864,
            "name": "Ciudad Autónoma de Buenos Aires",
            "department": "CABA",
            "province": "CABA",
            "type": "Ciudad",
            "coord": {"lon": -58.4258, "lat": -34.6217},
        },
        "type": "location",
        "forecast": [
            {
                "date": "2025-12-30",
                "temp_min": None,
                "temp_max": None,
                "night": {
                    "humidity": 30.0,
                    "temperature": 31.0,
                    "weather": {"description": "Parcialmente nublado", "id": 25},
                    "wind": {"direction": "NO", "deg": 315.0, "speed_range": [13, 22]},
                },
            },
            {
                "date": "2025-12-31",
                "temp_min": 27.0,
                "temp_max": 39.0,
                "morning": {
                    "humidity": 39.0,
                    "temperature": 31.0,
                    "weather": {"description": "Ligeramente nublado", "id": 13},
                    "wind": {"direction": "O", "deg": 292.5, "speed_range": [13, 22]},
                },
            },
        ],
    }


@pytest.fixture
def mock_alerts_data() -> dict:
    """Return mock alerts data with no active alerts (all level 1)."""
    return {
        "area_id": 762,
        "updated": "2025-12-30T17:33:07-03:00",
        "warnings": [
            {
                "date": "2025-12-30",
                "max_level": 1,
                "events": [
                    {"id": 37, "max_level": 1, "levels": {"night": 1}},
                    {"id": 54, "max_level": 1, "levels": {"night": 1}},
                ],
            }
        ],
        "reports": [],
    }


@pytest.fixture
def mock_alerts_data_with_active() -> dict:
    """Return mock alerts data with active alerts (for testing alert sensors)."""
    return {
        "area_id": 762,
        "updated": "2025-12-30T17:33:07-03:00",
        "warnings": [
            {
                "date": "2025-12-30",
                "max_level": 3,
                "events": [
                    {"id": 41, "max_level": 3, "levels": {"night": 3}},  # tormenta
                    {"id": 37, "max_level": 2, "levels": {"night": 2}},  # lluvia
                ],
            }
        ],
        "reports": [
            {
                "event_id": 41,
                "levels": [
                    {
                        "level": 3,
                        "description": "Tormentas fuertes",
                        "instruction": "Manténgase informado",
                    }
                ],
            },
            {
                "event_id": 37,
                "levels": [
                    {
                        "level": 2,
                        "description": "Lluvias moderadas",
                        "instruction": "Esté atento",
                    }
                ],
            },
        ],
    }


@pytest.fixture
def mock_shortterm_alerts() -> list:
    """Return mock short-term alerts data."""
    return [
        {
            "id": 30060,
            "title": "TORMENTAS FUERTES CON RAFAGAS Y CAIDA DE GRANIZO. ",
            "date": "2025-12-30T19:42:00-03:00",
            "end_date": "2025-12-30T20:42:00-03:00",
            "zones": ["BUENOS AIRES: Ayacucho - Balcarce - Mar Chiquita."],
            "severity": "N",
        }
    ]


@pytest.fixture
def mock_smn_api_client(
    mock_location_data,
    mock_current_weather,
    mock_forecast_data,
    mock_alerts_data,
    mock_shortterm_alerts,
) -> Generator[AsyncMock]:
    """Mock SMN API client."""
    with patch(
        "homeassistant.components.smn_argentina.coordinator.SMNApiClient",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.async_get_location = AsyncMock(return_value=mock_location_data)
        client.async_get_current_weather = AsyncMock(return_value=mock_current_weather)
        client.async_get_forecast = AsyncMock(return_value=mock_forecast_data)
        client.async_get_alerts = AsyncMock(return_value=mock_alerts_data)
        client.async_get_shortterm_alerts = AsyncMock(
            return_value=mock_shortterm_alerts
        )
        client.async_get_heat_warnings = AsyncMock(return_value={})

        yield client


@pytest.fixture
def mock_token_manager() -> Generator[AsyncMock]:
    """Mock the SMN token manager."""
    with patch(
        "homeassistant.components.smn_argentina.coordinator.SMNTokenManager"
    ) as mock_manager:
        manager_instance = mock_manager.return_value
        manager_instance.get_token = AsyncMock(
            return_value="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjk5OTk5OTk5OTl9.sig"
        )
        manager_instance.fetch_token = AsyncMock(
            return_value="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjk5OTk5OTk5OTl9.sig"
        )
        # Set token_expiration to far in the future so it doesn't trigger refresh
        manager_instance.token_expiration = datetime.now(UTC) + timedelta(hours=24)
        yield manager_instance
