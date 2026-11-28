"""Common fixtures for the TRMNL tests."""

from collections.abc import Generator
from time import time
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, load_fixture
from trmnl.models import DevicesResponse, OAuthToken, UserResponse

from homeassistant.components.trmnl.const import DOMAIN
from homeassistant.const import CONF_API_KEY

from . import ACCOUNT_SUBJECT


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.trmnl.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def expires_at() -> float:
    """Return when the access token expires."""
    return time() + 86400


@pytest.fixture
def mock_config_entry(expires_at: float) -> MockConfigEntry:
    """Mock config entry signed in with OAuth."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=2,
        title="TRMNL",
        unique_id=ACCOUNT_SUBJECT,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 7200,
                "token_type": "Bearer",
                "expires_at": expires_at,
            },
        },
    )


@pytest.fixture
def mock_api_key_config_entry() -> MockConfigEntry:
    """Mock version 1 config entry made with an account API key."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        title="Test",
        unique_id="30561",
        data={CONF_API_KEY: "user_aaaaaaaaaa"},
    )


@pytest.fixture
def mock_trmnl_client() -> Generator[AsyncMock]:
    """Mock TRMNL client."""
    with (
        patch(
            "homeassistant.components.trmnl.coordinator.TRMNLClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.trmnl.config_flow.TRMNLClient",
            new=mock_client,
        ),
        patch("homeassistant.components.trmnl.TRMNLClient", new=mock_client),
    ):
        client = mock_client.return_value
        client.get_me.return_value = UserResponse.from_json(
            load_fixture("me.json", DOMAIN)
        ).data
        client.get_devices.return_value = DevicesResponse.from_json(
            load_fixture("devices.json", DOMAIN)
        ).data
        client.migrate_to_oauth.return_value = OAuthToken.from_json(
            load_fixture("oauth_token.json", DOMAIN)
        )
        yield client
