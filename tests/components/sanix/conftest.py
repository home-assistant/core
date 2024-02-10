"""Sanix tests configuration."""

from unittest.mock import MagicMock, patch

import pytest

from tests.common import load_json_object_fixture


@pytest.fixture
def mock_sanix():
    """Build a fixture for the Sanix API that connects successfully and returns measurements."""
    measurements = load_json_object_fixture("sanix/get_measurements.json")
    mock_sanix_api = MagicMock()
    with patch(
        "homeassistant.components.sanix.config_flow.Sanix",
        return_value=mock_sanix_api,
    ) as mock_sanix_api, patch(
        "homeassistant.components.sanix.Sanix",
        return_value=mock_sanix_api,
    ):
        mock_sanix_api.return_value.fetch_data.return_value = measurements
        yield mock_sanix_api
