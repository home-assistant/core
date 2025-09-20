"""Test fixtures for the Actron Air Integration."""

from unittest.mock import patch

import pytest


@pytest.fixture
def mock_actron_api():
    """Mock the Actron Air API class."""
    with patch(
        "homeassistant.components.actron_air.config_flow.ActronNeoAPI", autospec=True
    ) as mock_api:
        yield mock_api
