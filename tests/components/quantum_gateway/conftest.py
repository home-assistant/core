"""Fixtures for Quantum Gateway tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.quantum_gateway.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SSL

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.0"
MOCK_SSL = True
MOCK_PASSWORD = "password"

MOCK_CONFIG = {CONF_HOST: MOCK_HOST, CONF_SSL: MOCK_SSL, CONF_PASSWORD: MOCK_PASSWORD}

MOCK_DEVICE_DATA = {
    "ff:ff:ff:ff:ff:ff": "",
    "ff:ff:ff:ff:ff:fe": "desktop",
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.quantum_gateway.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, title=f"UniFi AP ({MOCK_HOST})"
    )


@pytest.fixture
def mock_scanner() -> Generator[MagicMock]:
    """Mock QuantumGatewayScanner instance."""
    with (
        patch(
            "homeassistant.components.quantum_gateway.coordinator.QuantumGatewayScanner"
        ) as mock_scanner,
        patch(
            "homeassistant.components.quantum_gateway.config_flow.QuantumGatewayScanner",
            new=mock_scanner,
        ),
    ):
        client = MagicMock()
        client.success_init = True
        client.scan_devices.return_value = MOCK_DEVICE_DATA.keys()
        client.get_device_name.side_effect = MOCK_DEVICE_DATA.get

        mock_scanner.return_value = client
        yield mock_scanner
