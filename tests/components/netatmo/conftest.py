"""Provide common Netatmo fixtures."""
from contextlib import contextmanager
from time import time
from unittest.mock import patch

import pytest

from .common import ALL_SCOPES, TEST_TIME, fake_post_request, fake_post_request_no_data

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


@contextmanager
def selected_platforms(platforms=["camera", "climate", "light", "sensor"]):
    """Restrict loaded platforms to list given."""
    with patch("homeassistant.components.netatmo.PLATFORMS", platforms), patch(
        "homeassistant.components.netatmo.api.ConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.webhook.async_generate_url"
    ):
        mock_auth.return_value.post_request.side_effect = fake_post_request
        yield


@pytest.fixture(name="entry")
async def mock_entry_fixture(hass, config_entry):
    """Mock setup of all platforms."""
    with selected_platforms():
        await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()
    return config_entry


@pytest.fixture(name="sensor_entry")
async def mock_sensor_entry_fixture(hass, config_entry):
    """Mock setup of sensor platform."""
    with patch("time.time", return_value=TEST_TIME), selected_platforms(["sensor"]):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        yield config_entry


@pytest.fixture(name="camera_entry")
async def mock_camera_entry_fixture(hass, config_entry):
    """Mock setup of camera platform."""
    with selected_platforms(["camera"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()
    return config_entry


@pytest.fixture(name="light_entry")
async def mock_light_entry_fixture(hass, config_entry):
    """Mock setup of light platform."""
    with selected_platforms(["light"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()
    return config_entry


@pytest.fixture(name="climate_entry")
async def mock_climate_entry_fixture(hass, config_entry):
    """Mock setup of climate platform."""
    with selected_platforms(["climate"]):
        await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()
    return config_entry


@pytest.fixture(name="entry_error")
async def mock_entry_error_fixture(hass, config_entry):
    """Mock erroneous setup of platforms."""
    with patch(
        "homeassistant.components.netatmo.api.ConfigEntryNetatmoAuth"
    ) as mock_auth, patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ), patch(
        "homeassistant.components.webhook.async_generate_url"
    ):
        mock_auth.return_value.post_request.side_effect = fake_post_request_no_data
        await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()
        yield config_entry
