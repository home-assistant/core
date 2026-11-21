"""Test the Deluge integration setup."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.deluge.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import CONF_DATA, GET_TORRENT_STATES_RESPONSE, GET_TORRENT_STATUS_RESPONSE


def _mock_call(method: str, *args: Any) -> Any:
    """Answer the Deluge RPC calls the integration makes."""
    if method == "daemon.info":
        return b"2.1.1"
    if method == "core.get_session_status":
        return {
            key.encode(): value for key, value in GET_TORRENT_STATUS_RESPONSE.items()
        }
    return GET_TORRENT_STATES_RESPONSE


@pytest.fixture
def mock_deluge_client() -> Generator[MagicMock]:
    """Mock the Deluge RPC client."""
    with patch(
        "homeassistant.components.deluge.DelugeRPCClient", autospec=True
    ) as client_class:
        client = client_class.return_value
        client.host = CONF_DATA["host"]
        # The wire protocol deluge-client detected, not the daemon version
        client.deluge_version = 2
        client.call.side_effect = _mock_call
        yield client


@pytest.mark.usefixtures("mock_deluge_client")
async def test_device_sw_version(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test the device reports the daemon version as a string."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "2.1.1"
