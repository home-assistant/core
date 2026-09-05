"""Fixtures for the Willow integration tests."""

from collections.abc import Generator
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.willow.const import (
    DOMAIN,
    OAUTH2_CLIENT_ID,
    OAUTH2_CLIENT_SECRET,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

USER_ID = 42
ACCESS_TOKEN = "mock-access-token"
REFRESH_TOKEN = "mock-refresh-token"

# Willow imports its own client credential (in async_step_user) without an
# explicit auth_domain, so application_credentials defaults the auth_domain
# to the integration domain. That value is the auth_implementation stored on
# entries created by the flow.
IMPL_DOMAIN = DOMAIN


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
    with (
        patch(
            "homeassistant.components.willow.WillowClient", autospec=True
        ) as client_class,
        patch(
            "homeassistant.components.willow.config_flow.WillowClient",
            new=client_class,
        ),
    ):
        client = client_class.return_value
        client.get_profile.return_value = load_json_object_fixture(
            "profile.json", DOMAIN
        )
        client.get_devices.return_value = load_json_array_fixture(
            "devices.json", DOMAIN
        )
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
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET, name="Willow"),
    )
