"""Define fixtures for electric kiwi tests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
from time import time
from unittest.mock import AsyncMock, Mock, patch

from electrickiwi_api.model import AccountSummary, Hop, HopIntervals, Session
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

type YieldFixture = Generator[AsyncMock]
type ComponentSetup = Callable[[], Awaitable[bool]]


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup application credentials component."""
    await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture(name="electrickiwi_api")
def electrickiwi_api_fixture() -> AsyncMock:
    """Define electric kiwi API fixture."""
    return Mock(
        customer_number=123456,
        connection_id=123456,
        set_active_session=AsyncMock(None),
        get_active_session=AsyncMock(
            return_value=Session.from_dict(
                load_json_value_fixture("session.json", DOMAIN)
            )
        ),
        get_hop_intervals=AsyncMock(
            return_value=HopIntervals.from_dict(
                load_json_value_fixture("hop_intervals.json", DOMAIN)
            )
        ),
        get_hop=AsyncMock(
            return_value=Hop.from_dict(load_json_value_fixture("get_hop.json", DOMAIN))
        ),
        get_account_summary=AsyncMock(
            return_value=AccountSummary.from_dict(
                load_json_value_fixture("account_summary.json", DOMAIN)
            )
        ),
    )


@pytest.fixture(autouse=True)
def ek_api(electrickiwi_api: Mock) -> YieldFixture:
    """Mock ek api and return values."""
    with (
        patch(
            "electrickiwi_api.ElectricKiwiApi",
            autospec=True,
            return_value=electrickiwi_api,
        ),
        patch(
            "homeassistant.components.electric_kiwi.ElectricKiwiApi",
            autospec=True,
            return_value=electrickiwi_api,
        ),
    ):
        yield


async def init_integration(hass: HomeAssistant, entry: MockConfigEntry):
    """Fixture for setting up the integration with args."""
    hass.http = Mock()
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def component_setup(
    hass: HomeAssistant, config_entry: MockConfigEntry, ek_api: AsyncMock
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
    return MockConfigEntry(
        title="Electric Kiwi",
        domain=DOMAIN,
        data={
            "id": "123456",
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
        version=1,
        minor_version=1,
    )


@pytest.fixture(name="config_entry2")
def mock_config_entry2(hass: HomeAssistant) -> MockConfigEntry:
    """Create mocked config entry."""
    return MockConfigEntry(
        title="Electric Kiwi",
        domain=DOMAIN,
        data={
            "id": "123457",
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "expires_at": time() + 60,
            },
        },
        unique_id="1234567",
        version=1,
        minor_version=1,
    )


@pytest.fixture(name="migrated_config_entry")
def mock_migrated_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create mocked config entry."""
    return MockConfigEntry(
        title="Electric Kiwi",
        domain=DOMAIN,
        data={
            "id": "123456",
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "expires_at": time() + 60,
            },
        },
        unique_id="123456",
        version=1,
        minor_version=2,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.electric_kiwi.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(name="ek_auth")
def electric_kiwi_auth() -> YieldFixture:
    """Patch access to electric kiwi access token."""
    with patch(
        "homeassistant.components.electric_kiwi.api.ConfigEntryElectricKiwiAuth"
    ) as mock_auth:
        mock_auth.return_value.async_get_access_token = AsyncMock("auth_token")
        yield mock_auth
