"""Common fixtures for the SwitchBot via API tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.switchbot_cloud import SwitchBotAPI


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.switchbot_cloud.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_list_devices():
    """Mock list_devices."""
    with patch.object(SwitchBotAPI, "list_devices") as mock_list_devices:
        yield mock_list_devices


@pytest.fixture
def mock_get_status():
    """Mock get_status."""
    with patch.object(SwitchBotAPI, "get_status") as mock_get_status:
        yield mock_get_status
