"""Common fixtures for the Eltako Series 14 tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_serial_ports():
    """Override serial.tools.list_ports.comports."""
    mock_port = MagicMock()
    mock_port.device = "test_port"
    mock_port.description = "Test Serial Port"
    with patch(
        "homeassistant.components.eltako_series14.config_flow.serial.tools.list_ports.comports",
        return_value=[mock_port],
    ):
        yield


@pytest.fixture(autouse=True)
def mock_serial_for_url() -> Generator[Mock]:
    """Override serial.serial_for_url."""
    with patch(
        "homeassistant.components.eltako_series14.config_flow.serial.serial_for_url",
        return_value=True,
    ) as mock_serial_for_url:
        yield mock_serial_for_url


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.eltako_series14.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
