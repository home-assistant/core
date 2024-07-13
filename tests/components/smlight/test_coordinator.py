"""Tests for SMLIGHT coordinator."""

import socket
from unittest.mock import MagicMock

from pysmlight.exceptions import SmlightConnectionError
import pytest

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.util.network import is_ip_address

from .conftest import MOCK_HOST

from tests.common import MockConfigEntry

pytestmark = [
    pytest.mark.usefixtures(
        "setup_platform",
        "mock_smlight_client",
    )
]


async def test_coordinator_get_hostname(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test coordinator get hostname from IP."""
    coordinator = mock_config_entry.runtime_data

    def mock_gethostbyaddr(ip):
        if ip == "192.168.1.2":
            return (MOCK_HOST, [], ["192.168.1.2"])

        raise socket.herror("Host name lookup failure")

    monkeypatch.setattr(socket, "gethostbyaddr", mock_gethostbyaddr)

    host = coordinator.get_hostname("127.0.0.1")
    assert is_ip_address(host)
    assert host == "127.0.0.1"

    host = coordinator.get_hostname("192.168.1.2")
    assert not is_ip_address(host)
    assert host == "slzb-06"


async def test_coordinator_missing_creds(
    hass: HomeAssistant,
    mock_smlight_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator setup missing credentials.

    This will trigger reauth if user enables authentication on the SLZB device
    after initial setup.
    """
    mock_smlight_client.check_auth_needed.return_value = True
    mock_config_entry.data = {CONF_HOST: MOCK_HOST}

    coordinator = mock_config_entry.runtime_data
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator.async_maybe_auth()


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    mock_smlight_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator update failed."""
    mock_smlight_client.get_info.side_effect = SmlightConnectionError
    coordinator = mock_config_entry.runtime_data

    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
