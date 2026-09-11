"""Test fixtures for Bravia TV."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def silent_ssdp_scanner() -> Generator[None]:
    """Start SSDP component and get Scanner, prevent actual SSDP traffic."""
    with (
        patch("homeassistant.components.ssdp.Scanner._async_start_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner._async_stop_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner.async_scan"),
        patch(
            "homeassistant.components.ssdp.Server._async_start_upnp_servers",
        ),
        patch(
            "homeassistant.components.ssdp.Server._async_stop_upnp_servers",
        ),
    ):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.braviatv.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_bravia() -> Generator[AsyncMock]:
    """Mock BraviaClient class."""
    with (
        patch(
            "homeassistant.components.braviatv.BraviaClient", autospec=True
        ) as mock_class,
        patch(
            "homeassistant.components.braviatv.config_flow.BraviaClient",
            new=mock_class,
        ),
        patch(
            "homeassistant.components.braviatv.coordinator.BraviaClient",
            new=mock_class,
        ),
    ):
        yield mock_class


@pytest.fixture
def mock_bravia_client(mock_bravia: AsyncMock) -> AsyncMock:
    """Mock BraviaClient instance."""
    client = mock_bravia.return_value
    client.connect.return_value = None
    client.set_wol_mode.return_value = None
    client.get_power_status.return_value = "active"
    client.get_external_status.return_value = []
    client.get_app_list.return_value = []
    client.get_content_list_all.return_value = []
    client.get_volume_info.return_value = {}
    client.get_playing_info.return_value = {}
    client.send_rest_req.return_value = {}
    client.get_system_info.return_value = {
        "product": "TV",
        "region": "XEU",
        "language": "pol",
        "model": "TV-Model",
        "serial": "serial_number",
        "macAddr": "AA:BB:CC:DD:EE:FF",
        "name": "BRAVIA",
        "generation": "5.2.0",
        "area": "POL",
        "cid": "very_unique_string",
    }
    return client
