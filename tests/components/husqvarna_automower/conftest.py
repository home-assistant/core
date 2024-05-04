"""Test helpers for Husqvarna Automower."""

from collections.abc import Generator
import time
from unittest.mock import AsyncMock, patch

from aioautomower.utils import mower_list_to_dictionary_dataclass
from aiohttp import ClientWebSocketResponse
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import CLIENT_ID, CLIENT_SECRET, USER_ID

from tests.common import MockConfigEntry, load_fixture, load_json_value_fixture


@pytest.fixture(name="jwt")
def load_jwt_fixture():
    """Load Fixture data."""
    return load_fixture("jwt", DOMAIN)


@pytest.fixture(name="expires_at")
def mock_expires_at() -> float:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture
def mock_config_entry(jwt, expires_at: int) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Husqvarna Automower of Erika Mustermann",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": jwt,
                "scope": "iam:read amc:api",
                "expires_in": 86399,
                "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
                "provider": "husqvarna",
                "user_id": USER_ID,
                "token_type": "Bearer",
                "expires_at": expires_at,
            },
        },
        unique_id=USER_ID,
        entry_id="automower_test",
    )


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(
            CLIENT_ID,
            CLIENT_SECRET,
        ),
        DOMAIN,
    )


@pytest.fixture
def mock_automower_client() -> Generator[AsyncMock, None, None]:
    """Mock a Husqvarna Automower client."""
    with patch(
        "homeassistant.components.husqvarna_automower.AutomowerSession",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.get_status.return_value = mower_list_to_dictionary_dataclass(
            load_json_value_fixture("mower.json", DOMAIN)
        )

        async def websocket_connect() -> ClientWebSocketResponse:
            """Mock listen."""
            return ClientWebSocketResponse

        client.auth = AsyncMock(side_effect=websocket_connect)

        yield client
