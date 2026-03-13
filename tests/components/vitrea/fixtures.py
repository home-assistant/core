"""Test fixtures for vitrea integration."""

import json
from unittest.mock import MagicMock

import pytest
from vitreaclient.client import VitreaClient
from vitreaclient.constants import DeviceStatus, VitreaResponse


def load_fixture(filename: str) -> str:
    """Load a fixture file."""
    # This would normally load from a fixtures directory
    # For now, return sample data inline
    if filename == "vitrea_status_response.json":
        return json.dumps(
            {
                "switches": [
                    {"node": "01", "key": "01", "status": "O", "timer": ""},
                    {"node": "01", "key": "02", "status": "F", "timer": ""},
                    {"node": "02", "key": "01", "status": "O", "timer": "120"},
                ],
                "covers": [
                    {"node": "03", "key": "01", "position": "050"},
                    {"node": "03", "key": "02", "position": "100"},
                ],
            }
        )
    return "{}"


@pytest.fixture
def mock_vitrea_client() -> MagicMock:
    """Return a mocked VitreaClient instance."""
    client = MagicMock(spec=VitreaClient)
    client.connect.return_value = True
    client.disconnect.return_value = True
    client.get_status.return_value = [
        DeviceStatus(node="01", key="01", state="O", timer=None),
        DeviceStatus(node="02", key="01", state="O", timer=120),
        DeviceStatus(node="03", key="01", position="050"),
        DeviceStatus(node="03", key="02", position="100"),
    ]
    client.send_command.return_value = VitreaResponse(success=True)
    client.set_timer.return_value = VitreaResponse(success=True)
    return client


@pytest.fixture
def mock_vitrea_response() -> MagicMock:
    """Return a mocked VitreaResponse instance."""
    return MagicMock(spec=VitreaResponse)


@pytest.fixture
def mock_device_status() -> MagicMock:
    """Return a mocked DeviceStatus instance."""
    return MagicMock(spec=DeviceStatus)
