"""Common fixtures for the WireGuard tests."""
from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from ha_wireguard_api.model import WireGuardPeer
import pytest

from homeassistant.components.wireguard.const import DEFAULT_HOST, DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def fixture_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={CONF_HOST: DEFAULT_HOST},
        version=1,
    )


@pytest.fixture(name="setup_entry")
def fixture_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.wireguard.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(name="config_flow")
def fixture_config_flow() -> Generator[None, MagicMock, None]:
    """Return a mocked WireGuardApiClient."""
    with patch(
        "homeassistant.components.wireguard.config_flow.WireguardApiClient",
        autospec=True,
    ) as wg_mock:
        wg = wg_mock.return_value
        wg.host = DEFAULT_HOST
        wg.get_peers.return_value = [
            WireGuardPeer(
                name="EMPTY",
                endpoint=None,
                latest_handshake=None,
                transfer_rx=0,
                transfer_tx=0,
            ),
            WireGuardPeer(
                name="CONNECTED",
                endpoint="127.0.0.1:1234",
                latest_handshake=datetime(2024, 1, 1, tzinfo=UTC),
                transfer_rx=123,
                transfer_tx=456,
            ),
        ]
        yield wg


@pytest.fixture(name="coordinator_client")
def fixture_coordinator_client() -> Generator[None, MagicMock, None]:
    """Return a mocked WireGuardApiClient."""
    with patch(
        "homeassistant.components.wireguard.coordinator.WireguardApiClient",
        autospec=True,
    ) as wg_mock:
        wg = wg_mock.return_value
        wg.host = DEFAULT_HOST
        wg.get_peers.return_value = [
            WireGuardPeer(
                name="EMPTY",
                endpoint=None,
                latest_handshake=None,
                transfer_rx=0,
                transfer_tx=0,
            ),
            WireGuardPeer(
                name="CONNECTED",
                endpoint="127.0.0.1:1234",
                latest_handshake=datetime(2024, 1, 1, tzinfo=UTC),
                transfer_rx=123,
                transfer_tx=456,
            ),
        ]
        yield wg
