"""Fixtures for the Hase iQ integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyhaseiq import Phase, Status
import pytest

from homeassistant.components.hase_iq.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.165"


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Patch the pyhaseiq client, in both the coordinator and the config flow."""
    with (
        patch(
            "homeassistant.components.hase_iq.coordinator.Client", autospec=True
        ) as client_class,
        patch("homeassistant.components.hase_iq.config_flow.Client", new=client_class),
    ):
        client = client_class.return_value
        client.__aenter__.return_value = client
        client.get_phase.return_value = Phase.HEATING_UP
        client.get_status.return_value = Status(
            Phase.HEATING_UP, temperature=163.3, heat_up_percent=53.5
        )
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Stub out the entry setup, for config flow tests."""
    with patch(
        "homeassistant.components.hase_iq.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for the stove."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Hase iQ",
        data={CONF_HOST: MOCK_HOST},
        entry_id="01KPBBPM6WCQ8148EFR0TCG1WW",
    )
