"""Fixtures for the Concord232 integration."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_concord232_client() -> Generator[MagicMock]:
    """Mock the concord232 Client for easier testing."""
    with patch(
        "homeassistant.components.concord232.alarm_control_panel.concord232_client.Client"
    ) as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        # Set up default return values
        mock_instance.list_partitions.return_value = [{"arming_level": "Off"}]
        mock_instance.list_zones.return_value = [
            {"number": 1, "name": "Zone 1", "state": "Normal"},
            {"number": 2, "name": "Zone 2", "state": "Normal"},
        ]
        mock_instance.partitions = mock_instance.list_partitions.return_value

        yield mock_instance


@pytest.fixture
def mock_concord232_binary_sensor_client() -> Generator[MagicMock]:
    """Mock the concord232 Client for binary sensor testing."""
    with patch(
        "homeassistant.components.concord232.binary_sensor.concord232_client.Client"
    ) as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        # Set up default return values
        mock_instance.list_zones.return_value = [
            {"number": 1, "name": "Zone 1", "state": "Normal"},
            {"number": 2, "name": "Zone 2", "state": "Normal"},
        ]
        mock_instance.zones = mock_instance.list_zones.return_value

        yield mock_instance
