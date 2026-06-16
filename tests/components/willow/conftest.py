"""Fixtures for the Willow integration tests."""

from collections.abc import Generator
import copy
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
)
from homeassistant.components.willow.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

USER_ID = 42
ACCESS_TOKEN = "mock-access-token"
REFRESH_TOKEN = "mock-refresh-token"

# Willow imports its own client credential (in async_setup and async_step_user)
# without an explicit auth_domain, so application_credentials defaults the
# auth_domain to the integration domain. That value is the auth_implementation
# stored on entries created by the flow.
IMPL_DOMAIN = DOMAIN

PROFILE = {
    "id": USER_ID,
    "username": "garden@example.com",
    "profile_image": None,
}

DEVICES = [
    {
        "id": 1,
        "sensor_id": "SENSOR123",
        "battery_life": 88,
        "version": "1.2.3",
        "user_plant": {
            "id": 10,
            "name": "Basil",
            "location": "Kitchen",
        },
        "latest_reading": {
            "timestamp": "2026-05-08T12:00:00+00:00",
            "temperature": 21.5,
            "humidity": 55.0,
            "moisture": 30.0,
            "light": 1200.0,
        },
    }
]


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Bypass the integration setup so the config flow can be tested in isolation."""
    with patch(
        "homeassistant.components.willow.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_willow_client() -> Generator[MagicMock]:
    """Patch WillowClient wherever it is instantiated."""
    client = MagicMock()
    client.get_profile = AsyncMock(return_value=dict(copy.deepcopy(PROFILE)))
    client.get_devices = AsyncMock(
        return_value=[dict(copy.deepcopy(device)) for device in DEVICES]
    )
    with (
        patch("homeassistant.components.willow.WillowClient", return_value=client),
        patch(
            "homeassistant.components.willow.config_flow.WillowClient",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture(name="expires_at")
def mock_expires_at() -> float:
    """Fixture to set the OAuth token expiration time in the future."""
    return time.time() + 3600


@pytest.fixture
def mock_config_entry(expires_at: float) -> MockConfigEntry:
    """Return a Willow OAuth2 config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="garden@example.com",
        unique_id=str(USER_ID),
        data={
            "auth_implementation": IMPL_DOMAIN,
            "token": {
                "access_token": ACCESS_TOKEN,
                "refresh_token": REFRESH_TOKEN,
                "expires_at": expires_at,
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        },
        entry_id="01J5TX5A0FF6G5V0QJX6HBC94T",
    )


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Set up application_credentials so Willow can import its own credential.

    Willow registers its bundled OAuth2 client credential itself during
    ``async_setup`` and ``async_step_user``; this fixture only needs to ensure the
    application_credentials component is loaded so that import succeeds.
    """
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
