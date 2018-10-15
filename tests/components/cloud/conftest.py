"""Fixtures for cloud tests."""
import pytest

from . import mock_cloud, mock_cloud_prefs


@pytest.fixture
def mock_cloud_fixture(hass):
    """Fixture for cloud component."""
    mock_cloud(hass)
    return mock_cloud_prefs(hass)
