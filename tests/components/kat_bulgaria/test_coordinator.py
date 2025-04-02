"""Coordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

from kat_bulgaria.errors import KatError, KatErrorType
import pytest

from homeassistant.components.kat_bulgaria.config_flow import DOMAIN
from homeassistant.components.kat_bulgaria.kat_client import KatClient
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import Awaitable, Callable

from . import EGN_VALID, LICENSE_VALID, MOCK_DATA

from tests.common import MockConfigEntry


@pytest.fixture(name="platforms")
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR, Platform.SENSOR]


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(domain=DOMAIN, data=MOCK_DATA, unique_id=EGN_VALID)


@pytest.fixture(name="client")
def mock_client(hass: HomeAssistant, request: pytest.FixtureRequest) -> MagicMock:
    """Fixture to mock KatClient."""

    mock = KatClient(hass, "test", EGN_VALID, LICENSE_VALID)

    mock.get_obligations = AsyncMock(
        side_effect=[],
    )

    mock.side_effect = mock

    return mock


@pytest.fixture(name="client_api_timeout")
def mock_client_api_timeout(
    hass: HomeAssistant, request: pytest.FixtureRequest
) -> MagicMock:
    """Fixture to mock KatClient."""

    mock = KatClient(hass, "test", EGN_VALID, LICENSE_VALID)

    mock.get_obligations = AsyncMock(
        side_effect=KatError(KatErrorType.API_TIMEOUT, "error text"),
    )

    mock.side_effect = mock

    return mock


@pytest.fixture(name="integration_setup")
async def mock_integration_setup(
    hass: HomeAssistant,
    platforms: list[Platform],
    config_entry: MockConfigEntry,
) -> Callable[[MagicMock], Awaitable[bool]]:
    """Fixture to set up the integration."""
    config_entry.add_to_hass(hass)

    async def run(client: MagicMock) -> bool:
        with (
            patch("homeassistant.components.kat_bulgaria.PLATFORMS", platforms),
            patch(
                "homeassistant.components.kat_bulgaria.kat_client.KatClient"
            ) as client_mock,
        ):
            client_mock.return_value = client
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
        return result

    return run


async def test_coordinator_update_nodata(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    katclient_get_obligations_success_none,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.LOADED


async def test_coordinator_usernotfoundonline(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    katclient_get_obligations_usernotfoundonline,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_coordinator_api_timeout(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    katclient_get_obligations_api_timeout,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_coordinator_api_toomanyrequests(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    katclient_get_obligations_api_toomanyrequests,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_coordinator_api_invaliddata(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    katclient_get_obligations_api_errorreadingdata,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_coordinator_api_invalidschema(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    katclient_get_obligations_api_invalidschema,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_coordinator_api_unknownerror(
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    client: MagicMock,
    katclient_get_obligations_api_unknownerror,
) -> None:
    """Test that the coordinator can update."""
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    await integration_setup(client)
    assert config_entry.state == ConfigEntryState.SETUP_RETRY
