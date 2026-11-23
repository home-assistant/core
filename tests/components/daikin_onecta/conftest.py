"""Shared fixtures for the Daikin Onecta integration tests."""

import time
from unittest.mock import AsyncMock

from daikin_onecta import Site, get_account_id
from daikin_onecta.client import OnectaClient
from daikin_onecta.models import GatewayDevice
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.core import HomeAssistant


class MockOnectaClient:
    """Mocks for the Onecta client's cloud API methods."""

    def __init__(self) -> None:
        """Initialize the mock client and its recorded calls."""
        self.patch_characteristic = AsyncMock()
        self.get_gateway_devices = AsyncMock()
        self.get_sites = AsyncMock()
        self.post_management_point = AsyncMock()


@pytest.fixture
def mock_onecta_client(monkeypatch: pytest.MonkeyPatch) -> MockOnectaClient:
    """Mock calls made by the shared Onecta client."""
    mock_client = MockOnectaClient()

    async def mock_patch_characteristic(
        _client: object,
        gateway_id: str,
        management_point_id: str,
        characteristic: str,
        value: object,
        *,
        path: str | None = None,
    ) -> None:
        await mock_client.patch_characteristic(
            gateway_id,
            management_point_id,
            characteristic,
            value,
            path=path,
        )

    async def mock_get_gateway_devices(_client: object) -> list[GatewayDevice]:
        return await mock_client.get_gateway_devices()

    async def mock_get_sites(_client: object) -> list[Site]:
        return await mock_client.get_sites()

    async def mock_post_management_point(
        _client: object,
        gateway_id: str,
        management_point_id: str,
        resource: str,
        value: object,
    ) -> object:
        return await mock_client.post_management_point(
            gateway_id, management_point_id, resource, value
        )

    monkeypatch.setattr(
        "homeassistant.components.daikin_onecta.coordinator.OnectaClient.patch_characteristic",
        mock_patch_characteristic,
    )
    monkeypatch.setattr(
        "homeassistant.components.daikin_onecta.coordinator.OnectaClient.get_gateway_devices",
        mock_get_gateway_devices,
    )
    monkeypatch.setattr(OnectaClient, "get_sites", mock_get_sites)
    monkeypatch.setattr(
        "homeassistant.components.daikin_onecta.coordinator.OnectaClient.post_management_point",
        mock_post_management_point,
    )
    return mock_client


FAKE_ACCESS_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)
FAKE_REFRESH_TOKEN = "test-refresh-token"


@pytest.fixture(name="config_entry")
def mock_config_entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
    """Return a Daikin Onecta config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=get_account_id(FAKE_ACCESS_TOKEN),
        data={
            "auth_implementation": "cloud",
            "token": {
                "refresh_token": FAKE_REFRESH_TOKEN,
                "access_token": FAKE_ACCESS_TOKEN,
                "type": "Bearer",
                "expires_at": time.time() + 86400,
            },
        },
    )
    entry.add_to_hass(hass)
    return entry
