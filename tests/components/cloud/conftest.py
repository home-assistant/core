"""Fixtures for cloud tests."""
import pytest

from unittest.mock import patch

from . import mock_cloud, mock_cloud_prefs


@pytest.fixture(autouse=True)
def mock_user_data():
    """Mock os module."""
    with patch('hass_nabucasa.Cloud.write_user_info') as writer:
        yield writer


@pytest.fixture
def mock_cloud_fixture(hass):
    """Fixture for cloud component."""
    mock_cloud(hass)
    return mock_cloud_prefs(hass)
