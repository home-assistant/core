"""Test fixtures for fitbit."""

from collections.abc import Awaitable, Callable
import datetime
from http import HTTPStatus
import time
from typing import Any
from unittest.mock import patch

import pytest
from requests_mock.mocker import Mocker

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.fitbit.const import DOMAIN, OAUTH_SCOPES
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
PROFILE_USER_ID = "fitbit-api-user-id-1"
FAKE_ACCESS_TOKEN = "some-access-token"
FAKE_REFRESH_TOKEN = "some-refresh-token"
FAKE_AUTH_IMPL = "conftest-imported-cred"
FULL_NAME = "First Last"
DISPLAY_NAME = "First L."
PROFILE_DATA = {
    "fullName": FULL_NAME,
    "displayName": DISPLAY_NAME,
    "displayNameSetting": "name",
    "firstName": "First",
    "lastName": "Last",
}

PROFILE_API_URL = "https://api.fitbit.com/1/user/-/profile.json"
DEVICES_API_URL = "https://api.fitbit.com/1/user/-/devices.json"
TIMESERIES_API_URL_FORMAT = (
    "https://api.fitbit.com/1/user/-/{resource}/date/today/7d.json"
)

# These constants differ from values in the config entry or fitbit.conf
SERVER_ACCESS_TOKEN = {
    "refresh_token": "server-refresh-token",
    "access_token": "server-access-token",
    "type": "Bearer",
    "expires_in": 60,
    "scope": " ".join(OAUTH_SCOPES),
}


@pytest.fixture(name="token_expiration_time")
def mcok_token_expiration_time() -> float:
    """Fixture for expiration time of the config entry auth token."""
    return time.time() + 86400


@pytest.fixture(name="scopes")
def mock_scopes() -> list[str]:
    """Fixture for expiration time of the config entry auth token."""
    return OAUTH_SCOPES


@pytest.fixture(name="token_entry")
def mock_token_entry(token_expiration_time: float, scopes: list[str]) -> dict[str, Any]:
    """Fixture for OAuth 'token' data for a ConfigEntry."""
    return {
        "access_token": FAKE_ACCESS_TOKEN,
        "refresh_token": FAKE_REFRESH_TOKEN,
        "scope": " ".join(scopes),
        "token_type": "Bearer",
        "expires_at": token_expiration_time,
    }


@pytest.fixture(name="config_entry")
def mock_config_entry(
    token_entry: dict[str, Any], imported_config_data: dict[str, Any]
) -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": FAKE_AUTH_IMPL,
            "token": token_entry,
            **imported_config_data,
        },
        unique_id=PROFILE_USER_ID,
        title=DISPLAY_NAME,
    )


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        FAKE_AUTH_IMPL,
    )


@pytest.fixture(name="monitored_resources")
def mock_monitored_resources() -> list[str] | None:
    """Fixture for the fitbit yaml config monitored_resources field."""
    return None


@pytest.fixture(name="configured_unit_system")
def mock_configured_unit_syststem() -> str | None:
    """Fixture for the fitbit yaml config monitored_resources field."""
    return None


@pytest.fixture(name="imported_config_data")
def mock_imported_config_data(
    monitored_resources: list[str] | None,
    configured_unit_system: str | None,
) -> dict[str, Any]:
    """Fixture for the fitbit sensor platform configuration data in configuration.yaml."""
    config = {}
    if monitored_resources is not None:
        config["monitored_resources"] = monitored_resources
    if configured_unit_system is not None:
        config["unit_system"] = configured_unit_system
    return config


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture(name="integration_setup")
async def mock_integration_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    platforms: list[str],
) -> Callable[[], Awaitable[bool]]:
    """Fixture to set up the integration."""
    config_entry.add_to_hass(hass)

    async def run() -> bool:
        with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
        return result

    return run


@pytest.fixture(name="profile_id")
def mock_profile_id() -> str:
    """Fixture for the profile id returned from the API response."""
    return PROFILE_USER_ID


@pytest.fixture(name="profile_locale")
def mock_profile_locale() -> str:
    """Fixture to set the API response for the user profile."""
    return "en_US"


@pytest.fixture(name="profile_data")
def mock_profile_data() -> dict[str, Any]:
    """Fixture to return other profile data fields."""
    return PROFILE_DATA


@pytest.fixture(name="profile_response")
def mock_profile_response(
    profile_id: str, profile_locale: str, profile_data: dict[str, Any]
) -> dict[str, Any]:
    """Fixture to construct the fake profile API response."""
    return {
        "user": {
            "encodedId": profile_id,
            "locale": profile_locale,
            **profile_data,
        },
    }


@pytest.fixture(name="profile", autouse=True)
def mock_profile(requests_mock: Mocker, profile_response: dict[str, Any]) -> None:
    """Fixture to setup fake requests made to Fitbit API during config flow."""
    requests_mock.register_uri(
        "GET",
        PROFILE_API_URL,
        status_code=HTTPStatus.OK,
        json=profile_response,
    )


@pytest.fixture(name="devices_response")
def mock_device_response() -> list[dict[str, Any]]:
    """Return the list of devices."""
    return []


@pytest.fixture(autouse=True)
def mock_devices(requests_mock: Mocker, devices_response: dict[str, Any]) -> None:
    """Fixture to setup fake device responses."""
    requests_mock.register_uri(
        "GET",
        DEVICES_API_URL,
        status_code=HTTPStatus.OK,
        json=devices_response,
    )


def timeseries_response(resource: str, value: str) -> dict[str, Any]:
    """Create a timeseries response value."""
    return {
        resource: [{"dateTime": datetime.datetime.today().isoformat(), "value": value}]
    }


@pytest.fixture(name="register_timeseries")
def mock_register_timeseries(
    requests_mock: Mocker,
) -> Callable[[str, dict[str, Any]], None]:
    """Fixture to setup fake timeseries API responses."""

    def register(resource: str, response: dict[str, Any]) -> None:
        requests_mock.register_uri(
            "GET",
            TIMESERIES_API_URL_FORMAT.format(resource=resource),
            status_code=HTTPStatus.OK,
            json=response,
        )

    return register
