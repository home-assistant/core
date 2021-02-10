"""Provide common Netatmo fixtures."""
from time import time
from unittest.mock import patch

import pytest

from .common import ALL_SCOPES, fake_post_request, fake_post_request_no_data

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
async def mock_config_entry_fixture(hass):
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


@pytest.fixture(name="entry")
async def mock_entry_fixture(hass, config_entry):
    """Mock a component."""
    with patch(
        "homeassistant.components.netatmo.api.ConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.webhook.async_generate_url"
    ):
        mock_auth.return_value.post_request.side_effect = fake_post_request
        await hass.config_entries.async_setup(config_entry.entry_id)

    return config_entry


@pytest.fixture(name="sensor_entry")
async def mock_sensor_entry_fixture(hass, config_entry):
    """Mock a component."""
    with patch("homeassistant.components.netatmo.PLATFORMS", ["sensor"]), patch(
        "homeassistant.components.netatmo.api.ConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.webhook.async_generate_url"
    ):
        mock_auth.return_value.post_request.side_effect = fake_post_request
        await hass.config_entries.async_setup(config_entry.entry_id)

    return config_entry


@pytest.fixture(name="camera_entry")
async def mock_camera_entry_fixture(hass, config_entry):
    """Mock a component."""
    with patch("homeassistant.components.netatmo.PLATFORMS", ["camera"]), patch(
        "homeassistant.components.netatmo.api.ConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.webhook.async_generate_url"
    ):
        mock_auth.return_value.post_request.side_effect = fake_post_request
        await hass.config_entries.async_setup(config_entry.entry_id)

    return config_entry


@pytest.fixture(name="light_entry")
async def mock_light_entry_fixture(hass, config_entry):
    """Mock a component."""
    with patch("homeassistant.components.netatmo.PLATFORMS", ["light"]), patch(
        "homeassistant.components.netatmo.api.ConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.webhook.async_generate_url"
    ):
        mock_auth.return_value.post_request.side_effect = fake_post_request
        await hass.config_entries.async_setup(config_entry.entry_id)

    return config_entry


@pytest.fixture(name="climate_entry")
async def mock_climate_entry_fixture(hass, config_entry):
    """Mock a component."""
    with patch("homeassistant.components.netatmo.PLATFORMS", ["climate"]), patch(
        "homeassistant.components.netatmo.api.ConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.webhook.async_generate_url"
    ):
        mock_auth.return_value.post_request.side_effect = fake_post_request
        await hass.config_entries.async_setup(config_entry.entry_id)

    return config_entry


@pytest.fixture(name="entry_error")
async def mock_entry_error_fixture(hass, config_entry):
    """Mock a component."""
    with patch(
        "homeassistant.components.netatmo.api.ConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.webhook.async_generate_url"
    ):
        mock_auth.return_value.post_request.side_effect = fake_post_request_no_data
        await hass.config_entries.async_setup(config_entry.entry_id)

    return config_entry
