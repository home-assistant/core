"""Pytest fixtures for the Habitron integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

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
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Enable Habitron as a custom integration in every test."""
    return


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
        patch(
            "homeassistant.components.habitron.config_flow._get_local_ip",
            return_value="192.168.1.10",
        ),
        patch(
            "homeassistant.components.habitron.config_flow.ConfigFlow._discover_habitron",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "homeassistant.components.habitron.communicate.get_own_ip",
            return_value="192.168.1.10",
        ),
        patch(
            "homeassistant.components.habitron.communicate.get_host_ip",
            return_value=MOCK_HOST,
        ),
        patch(
            "homeassistant.components.habitron.communicate.HabitronClient",
            autospec=True,
        ) as mock_client_cls,
    ):
        mock_client = mock_client_cls.return_value
        mock_client.host = MOCK_HOST
        mock_client.send_network_info = MagicMock()
        yield mock_test


@pytest.fixture
def mock_smart_hub_setup() -> Generator[MagicMock]:
    """Stub ``SmartHub.async_setup`` so config-entry tests don't touch the bus.

    Populates the SmartHub instance with the field set the rest of the
    integration expects after a real ``async_setup`` would have run.
    """

    async def _async_setup(self) -> None:
        self._mac = MOCK_MAC
        self.uid = MOCK_UID
        self._version = MOCK_VERSION
        self._type = MOCK_HWTYPE
        self.host = MOCK_HOST
        self.addon_slug = ""
        self.base_url = f"http://{MOCK_HOST}:7780"
        self.router.b_uid = MOCK_UID
        self.router.modules = []
        self.router.states = []

    with patch(
        "homeassistant.components.habitron.smart_hub.SmartHub.async_setup",
        new=_async_setup,
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
    mock_smart_hub_setup: None,
    mock_coordinator_refresh: AsyncMock,
) -> MockConfigEntry:
    """Add and set up a Habitron config entry, returning the entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
