"""Test fixtures for the Home Assistant Hardware integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_zha_config_flow_setup() -> Generator[None]:
    """Mock the radio connection and probing of the ZHA config flow."""

    def mock_probe(config: dict[str, Any]) -> dict[str, Any]:
        # The radio probing will return the correct baudrate
        return {**config, "baudrate": 115200}

    mock_connect_app = MagicMock()
    mock_connect_app.__aenter__.return_value.backups.backups = [MagicMock()]
    mock_connect_app.__aenter__.return_value.backups.create_backup.return_value = (
        MagicMock()
    )

    with (
        patch(
            "bellows.zigbee.application.ControllerApplication.probe",
            side_effect=mock_probe,
        ),
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
