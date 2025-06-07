"""Fixtures for Quantum Gateway tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
async def mock_scanner() -> Generator[AsyncMock]:
    """Mock QuantumGatewayScanner instance."""
    with patch(
        "homeassistant.components.quantum_gateway.device_tracker.QuantumGatewayScanner",
        autospec=True,
    ) as mock_scanner:
        client = mock_scanner.return_value
        client.success_init = True
        client.scan_devices.return_value = ["ff:ff:ff:ff:ff:ff", "ff:ff:ff:ff:ff:fe"]
        client.get_device_name.side_effect = {
            "ff:ff:ff:ff:ff:ff": "",
            "ff:ff:ff:ff:ff:fe": "desktop",
        }.get
        yield mock_scanner
