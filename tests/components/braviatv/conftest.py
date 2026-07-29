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
