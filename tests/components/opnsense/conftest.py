"""Fixtures for OPNsense tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_opnsense_client():
    """Mock OPNsenseClient for all tests."""
    client = AsyncMock()
    client.get_arp = AsyncMock(return_value=[])
    client.get_interfaces = AsyncMock(return_value={"igb0": "WAN", "igb1": "LAN"})

    with (
        patch(
            "homeassistant.components.opnsense.OPNsenseClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.opnsense.config_flow.OPNsenseClient",
            return_value=client,
        ),
    ):
        yield client
