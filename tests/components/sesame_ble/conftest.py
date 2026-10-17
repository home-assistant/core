"""Fixtures for the Sesame BLE integration tests."""

from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant


@contextmanager
def _mock_process_uploaded_file(
    hass: HomeAssistant, file_id: str
) -> Generator[MagicMock]:
    yield MagicMock()


@pytest.fixture(autouse=True)
def mock_file_upload():
    """Mock process_uploaded_file and qrcode availability for QR upload tests."""
    with (
        patch(
            "homeassistant.components.sesame_ble.config_flow.process_uploaded_file",
            side_effect=_mock_process_uploaded_file,
        ),
        patch(
            "homeassistant.components.sesame_ble.config_flow._FILE_UPLOAD_AVAILABLE",
            True,
        ),
        patch(
            "homeassistant.components.sesame_ble.config_flow._QRCODE_AVAILABLE",
            True,
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture(autouse=True)
def mock_config_flow_sesame_device() -> Generator[MagicMock]:
    """Mock SesameDevice in config flow for connection and authentication."""
    with patch(
        "homeassistant.components.sesame_ble.config_flow.SesameDevice"
    ) as mock_dev_class:
        mock_device = MagicMock()
        mock_device.connect = AsyncMock()
        mock_device.login = AsyncMock()
        mock_device.disconnect = AsyncMock()
        mock_device.register = AsyncMock(
            return_value="0123456789abcdef0123456789abcdef"
        )
        mock_dev_class.return_value = mock_device
        yield mock_device
