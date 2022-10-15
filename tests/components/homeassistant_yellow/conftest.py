"""Test fixtures for the Home Assistant Yellow integration."""
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_zha_config_flow_setup() -> Generator[None, None, None]:
    """Mock the radio connection and probing of the ZHA config flow."""

    def mock_probe(config: dict[str, Any]) -> None:
        # The radio probing will return the correct baudrate
        return {**config, "baudrate": 115200}

    mock_connect_app = MagicMock()
    mock_connect_app.__aenter__.return_value.backups.backups = []

    with patch(
        "bellows.zigbee.application.ControllerApplication.probe", side_effect=mock_probe
    ), patch(
        "homeassistant.components.zha.config_flow.BaseZhaFlow._connect_zigpy_app",
        return_value=mock_connect_app,
    ), patch(
        "homeassistant.components.zha.async_setup_entry",
        return_value=True,
    ):
        yield
