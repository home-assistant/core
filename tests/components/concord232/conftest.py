"""Fixtures for the Concord232 integration."""

from collections.abc import Generator
from unittest.mock import MagicMock, create_autospec, patch

from concord232 import client as concord232_client
import pytest


@pytest.fixture
def mock_concord232_client_class() -> Generator[MagicMock]:
    """Mock the concord232 Client class for easier testing.

    One shared mock is patched into both platform import paths, so
    constructor calls from either platform are visible on the yielded
    class mock.
    """
    mock_client_class = create_autospec(concord232_client.Client)
    with (
        patch(
            "homeassistant.components.concord232.alarm_control_panel.concord232_client.Client",
            new=mock_client_class,
        ),
        patch(
            "homeassistant.components.concord232.binary_sensor.concord232_client.Client",
            new=mock_client_class,
        ),
    ):
        mock_instance = mock_client_class.return_value

        # Set up default return values
        mock_instance.list_partitions.return_value = [{"arming_level": "Off"}]
        mock_instance.list_zones.return_value = [
            {"number": 1, "name": "Zone 1", "state": "Normal"},
            {"number": 2, "name": "Zone 2", "state": "Normal"},
        ]

        yield mock_client_class


@pytest.fixture
def mock_concord232_client(mock_concord232_client_class: MagicMock) -> MagicMock:
    """Return the mocked concord232 client instance."""
    return mock_concord232_client_class.return_value
