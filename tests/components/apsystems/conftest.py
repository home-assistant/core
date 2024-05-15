"""Common fixtures for the APsystems Local API tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.apsystems.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_apsystems():
    """Override APsystemsEZ1M.get_device_info() to return MY_SERIAL_NUMBER as the serial number."""
    ret_data = MagicMock()
    ret_data.deviceId = "MY_SERIAL_NUMBER"
    with patch(
        "homeassistant.components.apsystems.config_flow.APsystemsEZ1M",
        return_value=AsyncMock(),
    ) as mock_api:
        mock_api.return_value.get_device_info.return_value = ret_data
        yield mock_api
