"""Define fixtures for electric kiwi tests."""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
from time import time
from unittest.mock import AsyncMock, patch
import zoneinfo

from electrickiwi_api.model import AccountBalance, Hop, HopIntervals
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.electric_kiwi.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_value_fixture

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
REDIRECT_URI = "https://example.com/auth/external/callback"

TZ_NAME = "Pacific/Auckland"
TIMEZONE = zoneinfo.ZoneInfo(TZ_NAME)
YieldFixture = Generator[AsyncMock, None, None]
ComponentSetup = Callable[[], Awaitable[bool]]


@pytest.fixture(autouse=True)
async def request_setup(current_request_with_host) -> None:
    """Request setup."""
    return


@pytest.fixture
def component_setup(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> ComponentSetup:
    """Fixture for setting up the integration."""

    async def _setup_func() -> bool:
        assert await async_setup_component(hass, "application_credentials", {})
        await hass.async_block_till_done()
        await async_import_client_credential(
            hass,
            DOMAIN,
            ClientCredential(CLIENT_ID, CLIENT_SECRET),
            DOMAIN,
        )
        await hass.async_block_till_done()
        config_entry.add_to_hass(hass)
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return result

    return _setup_func


@pytest.fixture(name="config_entry")
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create mocked config entry."""
    entry = MockConfigEntry(
        title="Electric Kiwi",
        domain=DOMAIN,
        data={
            "id": "12345",
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "expires_at": time() + 60,
            },
        },
        unique_id=DOMAIN,
    )
    return entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.electric_kiwi.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(name="ek_auth")
def electric_kiwi_auth() -> YieldFixture:
    """Patch access to electric kiwi access token."""
    with patch(
        "homeassistant.components.electric_kiwi.api.AsyncConfigEntryAuth"
    ) as mock_auth:
        mock_auth.return_value.async_get_access_token = AsyncMock("auth_token")
        yield mock_auth


@pytest.fixture(name="ek_api")
def ek_api() -> YieldFixture:
    """Mock ek api and return values."""
    with patch(
        "homeassistant.components.electric_kiwi.ElectricKiwiApi", autospec=True
    ) as mock_ek_api:
        mock_ek_api.return_value.customer_number = 123456
        mock_ek_api.return_value.connection_id = 123456
        mock_ek_api.return_value.set_active_session.return_value = None
        mock_ek_api.return_value.get_hop_intervals.return_value = (
            HopIntervals.from_dict(
                load_json_value_fixture("hop_intervals.json", DOMAIN)
            )
        )
        mock_ek_api.return_value.get_hop.return_value = Hop.from_dict(
            load_json_value_fixture("get_hop.json", DOMAIN)
        )
        mock_ek_api.return_value.get_account_balance.return_value = (
            AccountBalance.from_dict(
                load_json_value_fixture("account_balance.json", DOMAIN)
            )
        )
        yield mock_ek_api
