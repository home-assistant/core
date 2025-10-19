"""Common fixtures for the Xbox tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from xbox.webapi.api.provider.catalog.models import CatalogResponse
from xbox.webapi.api.provider.people.models import PeopleResponse
from xbox.webapi.api.provider.smartglass.models import (
    SmartglassConsoleList,
    SmartglassConsoleStatus,
)

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.xbox.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_object_fixture

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET), "imported-cred"
    )


@pytest.fixture(autouse=True)
def mock_oauth2_implementation() -> Generator[AsyncMock]:
    """Mock config entry oauth2 implementation."""
    with patch(
        "homeassistant.components.xbox.coordinator.config_entry_oauth2_flow.async_get_config_entry_implementation",
        return_value=AsyncMock(),
    ) as mock_client:
        client = mock_client.return_value

        yield client


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock Xbox configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Home Assistant Cloud",
        data={
            "auth_implementation": "cloud",
            "token": {
                "access_token": "1234567890",
                "expires_at": 1760697327.7298331,
                "expires_in": 3600,
                "refresh_token": "0987654321",
                "scope": "XboxLive.signin XboxLive.offline_access",
                "service": "xbox",
                "token_type": "bearer",
                "user_id": "AAAAAAAAAAAAAAAAAAAAA",
            },
        },
    )


@pytest.fixture(name="authentication_manager")
def mock_authentication_manager() -> Generator[AsyncMock]:
    """Mock xbox-webapi AuthenticationManager."""

    with (
        patch(
            "homeassistant.components.xbox.config_flow.AuthenticationManager",
            autospec=True,
        ) as mock_client,
    ):
        client = mock_client.return_value

        yield client


@pytest.fixture(name="signed_session")
def mock_signed_session() -> Generator[AsyncMock]:
    """Mock xbox-webapi SignedSession."""

    with (
        patch(
            "homeassistant.components.xbox.coordinator.SignedSession", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.xbox.config_flow.SignedSession", new=mock_client
        ),
    ):
        client = mock_client.return_value

        yield client


@pytest.fixture(name="xbox_live_client")
def mock_xbox_live_client(signed_session) -> Generator[AsyncMock]:
    """Mock xbox-webapi XboxLiveClient."""

    with (
        patch(
            "homeassistant.components.xbox.coordinator.XboxLiveClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.xbox.config_flow.XboxLiveClient", new=mock_client
        ),
    ):
        client = mock_client.return_value

        client.smartglass = AsyncMock()
        client.smartglass.get_console_list.return_value = SmartglassConsoleList(
            **load_json_object_fixture("smartglass_console_list.json", DOMAIN)
        )
        client.smartglass.get_console_status.return_value = SmartglassConsoleStatus(
            **load_json_object_fixture("smartglass_console_status.json", DOMAIN)
        )

        client.catalog = AsyncMock()
        client.catalog.get_product_from_alternate_id.return_value = CatalogResponse(
            **load_json_object_fixture("catalog_product_lookup.json", DOMAIN)
        )

        client.people = AsyncMock()
        client.people.get_friends_own_batch.return_value = PeopleResponse(
            **load_json_object_fixture("people_batch.json", DOMAIN)
        )
        client.people.get_friends_own.return_value = PeopleResponse(
            **load_json_object_fixture("people_friends_own.json", DOMAIN)
        )

        client.xuid = "271958441785640"

        yield client
