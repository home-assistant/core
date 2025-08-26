"""Test fixtures for the Home Assistant SkyConnect integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(name="mock_usb_serial_by_id", autouse=True)
def mock_usb_serial_by_id_fixture() -> Generator[MagicMock]:
    """Mock usb serial by id."""
    with patch(
        "homeassistant.components.zha.config_flow.usb.get_serial_by_id"
    ) as mock_usb_serial_by_id:
        mock_usb_serial_by_id.side_effect = lambda x: x
        yield mock_usb_serial_by_id


@pytest.fixture(autouse=True)
def mock_zha():
    """Mock the zha integration."""
    mock_connect_app = MagicMock()
    mock_connect_app.__aenter__.return_value.backups.backups = [MagicMock()]
    mock_connect_app.__aenter__.return_value.backups.create_backup.return_value = (
        MagicMock()
    )

    with (
        patch(
            "homeassistant.components.zha.radio_manager.ZhaRadioManager.connect_zigpy_app",
            return_value=mock_connect_app,
        ),
        patch(
            "homeassistant.components.zha.async_setup_entry",
            return_value=True,
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_zha_get_last_network_settings() -> Generator[None]:
    """Mock zha.api.async_get_last_network_settings."""

    with patch(
        "homeassistant.components.zha.api.async_get_last_network_settings",
        AsyncMock(return_value=None),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_usb_path_exists() -> Generator[None]:
    """Mock os.path.exists to allow the ZBT-1 integration to load."""
    with patch(
        "homeassistant.components.homeassistant_sky_connect.os.path.exists",
        return_value=True,
    ):
        yield
