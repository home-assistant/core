"""Common fixtures for the Nespresso Vertuo tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.nespresso_ble.const import DOMAIN

from . import ADDRESS, make_device

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        title="VL-MD1_26083MD1p00937820La",
    )


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto-enable bluetooth for all tests."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.nespresso_ble.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_update_device() -> Generator[AsyncMock]:
    """Mock the VMini update_device call."""
    with patch(
        "homeassistant.components.nespresso_ble.coordinator.VMiniBluetoothDeviceData.update_device",
        return_value=make_device(),
    ) as mock:
        yield mock
