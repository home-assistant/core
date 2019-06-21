"""Fixtures for cloud tests."""
import pytest

from unittest.mock import patch

from homeassistant.components.cloud import prefs

from . import mock_cloud, mock_cloud_prefs


@pytest.fixture(autouse=True)
def mock_user_data():
    """Mock os module."""
    with patch('hass_nabucasa.Cloud.write_user_info') as writer:
        yield writer


@pytest.fixture
def mock_cloud_fixture(hass):
    """Fixture for cloud component."""
    hass.loop.run_until_complete(mock_cloud(hass))
    return mock_cloud_prefs(hass)


@pytest.fixture
async def cloud_prefs(hass):
    """Fixture for cloud preferences."""
    cloud_prefs = prefs.CloudPreferences(hass)
    await cloud_prefs.async_initialize()
    return cloud_prefs
