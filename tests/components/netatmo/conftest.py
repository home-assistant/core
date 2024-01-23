"""Provide common Netatmo fixtures."""
from time import time
from unittest.mock import AsyncMock, patch

from pyatmo.const import ALL_SCOPES
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.netatmo.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import fake_get_image, fake_post_request

from tests.common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture(name="config_entry")
def mock_config_entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
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
                "scope": ALL_SCOPES,
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


@pytest.fixture(name="netatmo_auth")
def netatmo_auth() -> AsyncMock:
    """Restrict loaded platforms to list given."""
    with patch(
        "homeassistant.components.netatmo.api.AsyncConfigEntryNetatmoAuth"
    ) as mock_auth:
        mock_auth.return_value.async_post_request.side_effect = fake_post_request
        mock_auth.return_value.async_post_api_request.side_effect = fake_post_request
        mock_auth.return_value.async_get_image.side_effect = fake_get_image
        mock_auth.return_value.async_addwebhook.side_effect = AsyncMock()
        mock_auth.return_value.async_dropwebhook.side_effect = AsyncMock()
        yield
