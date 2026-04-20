"""Configuration for overkiz tests."""

from collections.abc import Awaitable, Callable, Generator
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, patch

from pyoverkiz.client import OverkizClient
from pyoverkiz.enums import APIType
from pyoverkiz.models import Event, OverkizServer, Setup
import pytest

from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import DEFAULT_SETUP_FIXTURE, load_setup_fixture
from .test_config_flow import TEST_EMAIL, TEST_GATEWAY_ID, TEST_PASSWORD, TEST_SERVER

from tests.common import MockConfigEntry

type SetupOverkizIntegration = Callable[..., Awaitable[MockConfigEntry]]


@dataclass
class MockOverkizClient(OverkizClient):
    """Mock Overkiz client used by integration tests."""

    setup: Setup = field(default_factory=load_setup_fixture)
    event_batches: list[list[Event]] = field(default_factory=list)
    server: OverkizServer = field(
        default_factory=lambda: OverkizServer(
            name="Somfy",
            endpoint="https://example.test/enduser-mobile-web/enduserAPI",
            manufacturer="Somfy",
            configuration_url=None,
        )
    )

    def __post_init__(self) -> None:
        """Initialize async client methods."""
        self._execution_id = 0
        self.api_type = APIType.CLOUD
        self.login = AsyncMock(return_value=True)
        self.get_setup = AsyncMock(side_effect=self._async_get_setup)
        self.get_devices = AsyncMock(side_effect=self._async_get_devices)
        self.get_scenarios = AsyncMock(return_value=[])
        self.fetch_events = AsyncMock(side_effect=self._async_fetch_events)
        self.get_current_executions = AsyncMock(return_value=[])
        self.cancel_command = AsyncMock(return_value=None)
        self.execute_command = AsyncMock(side_effect=self._async_execute_command)

    def set_setup_fixture(self, fixture: str) -> None:
        """Load a setup fixture for the next integration setup."""
        self.setup = load_setup_fixture(fixture)
        self.event_batches.clear()
        self.reset_mock()

    def queue_events(self, *batches: list[Event]) -> None:
        """Queue batches of events returned by fetch_events."""
        self.event_batches.extend(batches)

    def reset_mock(self) -> None:
        """Reset call history while keeping configured behavior."""
        self.login.reset_mock()
        self.get_setup.reset_mock()
        self.get_devices.reset_mock()
        self.get_scenarios.reset_mock()
        self.fetch_events.reset_mock()
        self.get_current_executions.reset_mock()
        self.cancel_command.reset_mock()
        self.execute_command.reset_mock()

    async def _async_get_setup(self) -> Setup:
        """Return the configured setup."""
        return self.setup

    async def _async_get_devices(self, refresh: bool = False) -> list:
        """Return the configured devices."""
        return self.setup.devices

    async def _async_fetch_events(self) -> list[Event]:
        """Return queued event batches one refresh at a time."""
        if self.event_batches:
            return self.event_batches.pop(0)
        return []

    async def _async_execute_command(self, *args, **kwargs) -> str:
        """Return a unique execution id for each command."""
        self._execution_id += 1
        return f"exec-{self._execution_id}"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Somfy TaHoma Switch",
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_SERVER},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.overkiz.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_client() -> MockOverkizClient:
    """Return a configurable mock Overkiz client."""
    return MockOverkizClient()


@pytest.fixture
def setup_overkiz_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MockOverkizClient,
) -> SetupOverkizIntegration:
    """Return a helper to set up the Overkiz integration from a chosen fixture."""

    async def _setup(
        *,
        fixture: str = DEFAULT_SETUP_FIXTURE,
    ) -> MockConfigEntry:
        mock_config_entry.add_to_hass(hass)

        mock_client.set_setup_fixture(fixture)

        with (
            patch(
                "homeassistant.components.overkiz.create_cloud_client",
                return_value=mock_client,
            ),
            patch(
                "homeassistant.components.overkiz.create_local_client",
                return_value=mock_client,
            ),
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        return mock_config_entry

    return _setup


@pytest.fixture
async def init_integration(
    setup_overkiz_integration: SetupOverkizIntegration,
) -> MockConfigEntry:
    """Set up the Overkiz integration for testing."""
    return await setup_overkiz_integration()
