"""Test fixtures for the cast integration."""
# pylint: disable=protected-access
from unittest.mock import AsyncMock, MagicMock, patch

import pychromecast
import pytest


@pytest.fixture()
def dial_mock():
    """Mock pychromecast dial."""
    dial_mock = MagicMock()
    dial_mock.get_device_status.return_value.uuid = "fake_uuid"
    dial_mock.get_device_status.return_value.manufacturer = "fake_manufacturer"
    dial_mock.get_device_status.return_value.model_name = "fake_model_name"
    dial_mock.get_device_status.return_value.friendly_name = "fake_friendly_name"
    dial_mock.get_multizone_status.return_value.dynamic_groups = []
    return dial_mock


@pytest.fixture()
def castbrowser_mock():
    """Mock pychromecast CastBrowser."""
    return MagicMock()


@pytest.fixture()
def castbrowser_constructor_mock():
    """Mock pychromecast CastBrowser constructor."""
    return MagicMock()


@pytest.fixture()
def mz_mock():
    """Mock pychromecast MultizoneManager."""
    return MagicMock()


@pytest.fixture()
def pycast_mock(castbrowser_mock, castbrowser_constructor_mock):
    """Mock pychromecast."""
    pycast_mock = MagicMock()
    pycast_mock.IGNORE_CEC = []
    pycast_mock.discovery.CastBrowser = castbrowser_constructor_mock
    pycast_mock.discovery.CastBrowser.return_value = castbrowser_mock
    pycast_mock.discovery.AbstractCastListener = (
        pychromecast.discovery.AbstractCastListener
    )
    return pycast_mock


@pytest.fixture()
def quick_play_mock():
    """Mock pychromecast quick_play."""
    return MagicMock()


@pytest.fixture(autouse=True)
def cast_mock(dial_mock, mz_mock, pycast_mock, quick_play_mock):
    """Mock pychromecast."""
    with patch(
        "homeassistant.components.cast.media_player.pychromecast", pycast_mock
    ), patch(
        "homeassistant.components.cast.discovery.pychromecast", pycast_mock
    ), patch(
        "homeassistant.components.cast.helpers.dial", dial_mock
    ), patch(
        "homeassistant.components.cast.media_player.MultizoneManager",
        return_value=mz_mock,
    ), patch(
        "homeassistant.components.cast.media_player.zeroconf.async_get_instance",
        AsyncMock(),
    ), patch(
        "homeassistant.components.cast.media_player.quick_play",
        quick_play_mock,
    ):
        yield
