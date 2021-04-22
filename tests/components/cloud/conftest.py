"""Fixtures for cloud tests."""
from unittest.mock import patch

import jwt
import pytest

from homeassistant.components.cloud import const, prefs

from . import mock_cloud, mock_cloud_prefs


@pytest.fixture(autouse=True)
def mock_user_data():
    """Mock os module."""
    with patch("hass_nabucasa.Cloud.write_user_info") as writer:
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


@pytest.fixture
async def mock_cloud_setup(hass):
    """Set up the cloud."""
    await mock_cloud(hass)


@pytest.fixture
def mock_cloud_login(hass, mock_cloud_setup):
    """Mock cloud is logged in."""
    hass.data[const.DOMAIN].id_token = jwt.encode(
        {
            "email": "hello@home-assistant.io",
            "custom:sub-exp": "2300-01-03",
            "cognito:username": "abcdefghjkl",
        },
        "test",
    )


@pytest.fixture
def mock_expired_cloud_login(hass, mock_cloud_setup):
    """Mock cloud is logged in."""
    hass.data[const.DOMAIN].id_token = jwt.encode(
        {
            "email": "hello@home-assistant.io",
            "custom:sub-exp": "2018-01-01",
            "cognito:username": "abcdefghjkl",
        },
        "test",
    )
