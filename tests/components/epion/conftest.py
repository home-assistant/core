"""Epion tests configuration."""

from unittest.mock import MagicMock, patch

import pytest

from tests.common import load_json_object_fixture


@pytest.fixture
def mock_epion():
    """Build a fixture for the Epion API that connects successfully and returns one device."""
    current_one_device_data = load_json_object_fixture(
        "epion/get_current_one_device.json"
    )
    mock_epion_api = MagicMock()
    with (
        patch(
            "homeassistant.components.epion.config_flow.Epion",
            return_value=mock_epion_api,
        ) as mock_epion_api,
        patch(
            "homeassistant.components.epion.Epion",
            return_value=mock_epion_api,
        ),
    ):
        mock_epion_api.return_value.get_current.return_value = current_one_device_data
        yield mock_epion_api
