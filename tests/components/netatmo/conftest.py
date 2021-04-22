"""Provide common Netatmo fixtures."""
from time import time

import pytest

from .common import ALL_SCOPES

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def mock_config_entry_fixture(hass):
    """Mock a config entry."""
    mock_entry = MockConfigEntry(
        domain="netatmo",
        data={
            "auth_implementation": "cloud",
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "expires_at": time() + 1000,
                "scope": " ".join(ALL_SCOPES),
            },
        },
        options={
            "weather_areas": {
                "Home avg": {
                    "lat_ne": 32.2345678,
                    "lon_ne": -117.1234567,
                    "lat_sw": 32.1234567,
                    "lon_sw": -117.2345678,
                    "show_on_map": False,
                    "area_name": "Home avg",
                    "mode": "avg",
                },
                "Home max": {
                    "lat_ne": 32.2345678,
                    "lon_ne": -117.1234567,
                    "lat_sw": 32.1234567,
                    "lon_sw": -117.2345678,
                    "show_on_map": True,
                    "area_name": "Home max",
                    "mode": "max",
                },
            }
        },
    )
    mock_entry.add_to_hass(hass)

    return mock_entry
