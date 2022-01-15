"""Test fixtures for the cast integration."""
# pylint: disable=protected-access
from unittest.mock import AsyncMock, MagicMock, patch

import pychromecast
import pytest


@pytest.fixture()
def get_multizone_status_mock():
    """Mock pychromecast dial."""
    mock = MagicMock(spec_set=pychromecast.dial.get_multizone_status)
    mock.return_value.dynamic_groups = []
    return mock


@pytest.fixture()
def castbrowser_mock():
    """Mock pychromecast CastBrowser."""
    return MagicMock(spec=pychromecast.discovery.CastBrowser)


@pytest.fixture()
def mz_mock():
    """Mock pychromecast MultizoneManager."""
    return MagicMock(spec_set=pychromecast.controllers.multizone.MultizoneManager)


@pytest.fixture()
def quick_play_mock():
    """Mock pychromecast quick_play."""
    return MagicMock()


@pytest.fixture()
def get_chromecast_mock():
    """Mock pychromecast get_chromecast_from_cast_info."""
    return MagicMock()


@pytest.fixture(autouse=True)
def cast_mock(
    mz_mock,
    quick_play_mock,
    castbrowser_mock,
    get_chromecast_mock,
    get_multizone_status_mock,
):
    """Mock pychromecast."""
    ignore_cec_orig = list(pychromecast.IGNORE_CEC)

    with patch(
        "homeassistant.components.cast.discovery.pychromecast.discovery.CastBrowser",
        castbrowser_mock,
    ), patch(
        "homeassistant.components.cast.helpers.dial.get_multizone_status",
        get_multizone_status_mock,
    ), patch(
        "homeassistant.components.cast.media_player.MultizoneManager",
        return_value=mz_mock,
    ), patch(
        "homeassistant.components.cast.media_player.zeroconf.async_get_instance",
        AsyncMock(),
    ), patch(
        "homeassistant.components.cast.media_player.quick_play",
        quick_play_mock,
    ), patch(
        "homeassistant.components.cast.media_player.pychromecast.get_chromecast_from_cast_info",
        get_chromecast_mock,
    ):
        yield

    pychromecast.IGNORE_CEC = list(ignore_cec_orig)
