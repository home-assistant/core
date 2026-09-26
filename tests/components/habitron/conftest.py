"""Pytest fixtures for the Habitron integration."""

from collections.abc import Generator
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, MagicMock, patch

from habitron_client import SmartHub
import pytest

from homeassistant.components.habitron.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import (
    MOCK_CONFIG_DATA,
    MOCK_CONFIG_OPTIONS,
    MOCK_HOST,
    MOCK_HWTYPE,
    MOCK_MAC,
    MOCK_NAME,
    MOCK_UID,
    MOCK_VERSION,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_hub_mac() -> Generator[AsyncMock]:
    """Report a MAC unless a test says otherwise.

    The config flow probes the hub for its MAC, which is the only identity it
    keys on, so without this every flow test would open a real socket. A hub
    that answers reports one; a test for the "no MAC" path sets
    ``mock_hub_mac.return_value = None``.
    """
    with patch(
        "homeassistant.components.habitron.config_flow._async_hub_mac",
        new=AsyncMock(return_value=MOCK_UID),
    ) as mock:
        yield mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Build a ready-to-add Habitron config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_NAME,
        unique_id=MOCK_UID,
        data=MOCK_CONFIG_DATA,
        options=MOCK_CONFIG_OPTIONS,
    )


@pytest.fixture
def mock_habitron_client() -> Generator[MagicMock]:
    """Patch the ``habitron_client`` package surface used by the integration.

    ``test_connection`` is the connect-probe used by the config flow; the
    rest of the API surface (``HabitronClient``, IP helpers) is stubbed
    with no-op MagicMocks so the integration imports cleanly without a
    real hub.
    """
    with (
        patch(
            "homeassistant.components.habitron.config_flow.test_connection",
            new=AsyncMock(return_value=(True, MOCK_NAME)),
        ) as mock_test,
        # ``validate_input`` resolves the host first (to tell an unresolvable
        # name apart from a connection failure); stub it so tests don't hit DNS.
        patch(
            "homeassistant.components.habitron.config_flow.get_host_ip",
            new=AsyncMock(return_value=MOCK_HOST),
        ),
        patch(
            "homeassistant.components.habitron.config_flow.network.async_get_source_ip",
            new=AsyncMock(return_value="192.168.1.10"),
        ),
        patch(
            "homeassistant.components.habitron.config_flow.network."
            "async_get_enabled_source_ips",
            new=AsyncMock(return_value=[IPv4Address("192.168.1.10")]),
        ),
        patch(
            "homeassistant.components.habitron.config_flow.discover_smarthubs",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.habitron.coordinator.get_own_ip",
            return_value="192.168.1.10",
        ),
        patch(
            "homeassistant.components.habitron.coordinator.get_host_ip",
            new=AsyncMock(return_value=MOCK_HOST),
        ),
        patch(
            "homeassistant.components.habitron.coordinator.HabitronClient",
            autospec=True,
        ) as mock_client_cls,
    ):
        mock_client = mock_client_cls.return_value
        mock_client.host = MOCK_HOST
        mock_client.send_network_info = MagicMock()
        yield mock_test


@pytest.fixture
def mock_coordinator_setup() -> Generator[MagicMock]:
    """Stub the coordinator's connect/build so tests don't touch the bus.

    Populates the coordinator with the field set the rest of the integration
    expects after a real ``_async_connect_and_build`` would have run.
    """

    async def _connect_and_build(self) -> None:
        self.host = MOCK_HOST
        self.hub = SmartHub(
            uid=MOCK_UID,
            lan_mac=MOCK_MAC,
            macs=[MOCK_MAC],
            platform=MOCK_HWTYPE,
            version=MOCK_VERSION,
        )
        self._uid_from_mac = True
        self.base_url = f"http://{MOCK_HOST}:7780"
        self.router.modules = []
        self.router.states = []

    with patch(
        "homeassistant.components.habitron.coordinator."
        "HbtnCoordinator._async_connect_and_build",
        new=_connect_and_build,
    ):
        yield


@pytest.fixture
def mock_coordinator_refresh() -> Generator[AsyncMock]:
    """Skip the first refresh so coordinator setup completes without a hub."""
    with patch(
        "homeassistant.helpers.update_coordinator."
        "DataUpdateCoordinator.async_config_entry_first_refresh",
        new=AsyncMock(),
    ) as mock:
        yield mock


@pytest.fixture
async def setup_homeassistant(hass: HomeAssistant) -> None:
    """Load the ``homeassistant`` core component before every test.

    ``conversation`` (a transitive dependency via ``assist_pipeline``)
    expects ``hass.data['homeassistant.exposed_entities']`` to be
    populated by the core component's setup. Without it any test that
    causes habitron to attempt setup — even indirectly through
    listeners — fails on the dependency chain.
    """
    assert await async_setup_component(hass, "homeassistant", {})


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_config_entry: MockConfigEntry,
    mock_habitron_client: MagicMock,
    mock_coordinator_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> MockConfigEntry:
    """Add and set up a Habitron config entry, returning the entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
