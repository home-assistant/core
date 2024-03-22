"""Common fixtures for the Arctic Spa tests."""
from unittest.mock import MagicMock, patch

import pytest

from tests.common import load_json_object_fixture
from tests.components.arcticspa import API_ID


@pytest.fixture
def mock_arcticspa():
    """Build a fixture for the ArcticSpa API that connects successfully and returns one device."""
    device_data = load_json_object_fixture("arcticspa/status.json")
    mock_arcticspa_device = MagicMock()
    with patch(
        "homeassistant.components.arcticspa.config_flow.Spa",
        return_value=mock_arcticspa_device,
    ) as mock_arcticspa_device, patch(
        "homeassistant.components.arcticspa.Spa",
        return_value=mock_arcticspa_device,
    ):
        mock_arcticspa_device.return_value.status.return_value = device_data
        mock_arcticspa_device.return_value.id = API_ID
        yield mock_arcticspa_device
