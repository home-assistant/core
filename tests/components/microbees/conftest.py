"""Conftest for microBees tests."""

import time
from unittest.mock import AsyncMock, patch

from microBeesPy import Bee, MicroBees, Profile
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.microbees.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
TITLE = "MicroBees"
MICROBEES_AUTH_URI = "https://dev.microbees.com/oauth/authorize"
MICROBEES_TOKEN_URI = "https://dev.microbees.com/oauth/token"

SCOPES = ["read", "write"]


@pytest.fixture(name="scopes")
def mock_scopes() -> list[str]:
    """Fixture to set the scopes present in the OAuth token."""
    return SCOPES


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        DOMAIN,
    )


@pytest.fixture(name="expires_at")
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture(name="config_entry")
def mock_config_entry(expires_at: int, scopes: list[str]) -> MockConfigEntry:
    """Create YouTube entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id=54321,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": " ".join(scopes),
            },
        },
    )


@pytest.fixture(name="microbees")
def mock_microbees():
    """Mock microbees."""

    devices_json = load_json_array_fixture("microbees/bees.json")
    devices = [Bee.from_dict(device) for device in devices_json]
    profile_json = load_json_object_fixture("microbees/profile.json")
    profile = Profile.from_dict(profile_json)
    mock = AsyncMock(spec=MicroBees)
    mock.getBees.return_value = devices
    mock.getMyProfile.return_value = profile

    with (
        patch(
            "homeassistant.components.microbees.config_flow.MicroBees",
            return_value=mock,
        ) as mock,
        patch(
            "homeassistant.components.microbees.MicroBees",
            return_value=mock,
        ),
    ):
        yield mock
