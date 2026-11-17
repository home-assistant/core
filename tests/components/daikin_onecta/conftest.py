"""Shared fixtures for the Daikin Onecta integration tests."""

from collections.abc import Awaitable, Callable
import time
from typing import cast
from unittest.mock import AsyncMock, MagicMock

from daikin_onecta import ClimateControlClient, OnectaClient, get_account_id
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.core import HomeAssistant


class MockOnectaClient:
    """Shared library-client mock for Daikin climate command tests."""

    def __init__(self) -> None:
        """Initialize the mock client and its recorded calls."""
        self.patch_characteristic = AsyncMock()
        self.post_management_point = AsyncMock()
        self.client = MagicMock()
        self.client.patch_characteristic = self.patch_characteristic
        self.client.post_management_point = self.post_management_point
        self.client.climate_control.side_effect = (
            lambda gateway_id, management_point_id: ClimateControlClient(
                self.client, gateway_id, management_point_id
            )
        )

    def bind_coordinator(
        self, coordinator: MagicMock, device: MagicMock | None = None
    ) -> None:
        """Route a lightweight coordinator mock through the shared client."""
        result = True

        async def patch_characteristic(
            gateway_id: str,
            management_point_id: str,
            characteristic: str,
            value: object,
            *,
            path: str | None = None,
        ) -> None:
            nonlocal result
            if device is not None and isinstance(device.patch, AsyncMock):
                result = bool(
                    await device.patch(
                        gateway_id,
                        management_point_id,
                        characteristic,
                        path or "",
                        value,
                    )
                )
            else:
                result = True

        async def execute_command(
            command: Callable[[OnectaClient], Awaitable[None]],
        ) -> bool:
            nonlocal result
            result = True
            self.patch_characteristic.side_effect = patch_characteristic
            await command(cast("OnectaClient", self.client))
            return result

        coordinator.async_execute_command = AsyncMock(side_effect=execute_command)


@pytest.fixture
def mock_onecta_client(monkeypatch: pytest.MonkeyPatch) -> MockOnectaClient:
    """Mock writes made by the shared Onecta client."""
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

    monkeypatch.setattr(
        "homeassistant.components.daikin_onecta.coordinator.OnectaClient.patch_characteristic",
        mock_patch_characteristic,
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
