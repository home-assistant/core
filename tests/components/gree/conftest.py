"""Pytest module configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.gree.const import DISCOVERY_TIMEOUT

from .common import FakeDiscovery, build_device_mock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.gree.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True, name="discovery")
def discovery_fixture(device: MagicMock) -> Generator[MagicMock]:
    """Give each scan an independent transport and shared configurable replies."""
    with patch("homeassistant.components.gree.discovery.Discovery") as mock:
        mock.mock_devices = [device()]
        mock.instances = []

        def create_discovery(timeout: int = DISCOVERY_TIMEOUT) -> FakeDiscovery:
            scanner = FakeDiscovery(timeout, mock_devices=mock.mock_devices)
            mock.instances.append(scanner)
            return scanner

        mock.side_effect = create_discovery
        yield mock


@pytest.fixture(autouse=True, name="device")
def device_fixture() -> Generator[MagicMock]:
    """Patch setup and validation devices without sharing discovery ownership."""
    with (
        patch(
            "homeassistant.components.gree.coordinator.Device",
            return_value=build_device_mock(),
        ) as mock,
        patch("homeassistant.components.gree.config_flow.Device", mock),
    ):
        yield mock
