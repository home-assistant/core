"""Fixtures for Samsung TV."""
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from samsungctl import Remote
from samsungtvws.async_remote import SamsungTVWSAsyncRemote

import homeassistant.util.dt as dt_util

from .const import SAMPLE_APP_LIST, SAMPLE_DEVICE_INFO_WIFI


@pytest.fixture(autouse=True)
def fake_host_fixture() -> None:
    """Patch gethostbyname."""
    with patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
        yield


@pytest.fixture(name="remote")
def remote_fixture() -> Mock:
    """Patch the samsungctl Remote."""
    with patch("homeassistant.components.samsungtv.bridge.Remote") as remote_class:
        remote = Mock(Remote)
        remote.__enter__ = Mock()
        remote.__exit__ = Mock()
        remote_class.return_value = remote
        yield remote


@pytest.fixture(name="rest_api", autouse=True)
def rest_api_fixture() -> Mock:
    """Patch the samsungtvws SamsungTVAsyncRest."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVAsyncRest",
        autospec=True,
    ) as rest_api_class:
        rest_api_class.return_value.rest_device_info.return_value = (
            SAMPLE_DEVICE_INFO_WIFI
        )
        yield rest_api_class.return_value


@pytest.fixture(name="remotews")
def remotews_fixture() -> Mock:
    """Patch the samsungtvws SamsungTVWS."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncRemote",
    ) as remotews_class:
        remotews = Mock(SamsungTVWSAsyncRemote)
        remotews.__aenter__ = AsyncMock(return_value=remotews)
        remotews.__aexit__ = AsyncMock()
        remotews.app_list.return_value = SAMPLE_APP_LIST
        remotews.token = "FAKE_TOKEN"
        remotews_class.return_value = remotews
        yield remotews


@pytest.fixture(name="delay")
def delay_fixture() -> Mock:
    """Patch the delay script function."""
    with patch(
        "homeassistant.components.samsungtv.media_player.Script.async_run"
    ) as delay:
        yield delay


@pytest.fixture
def mock_now() -> datetime:
    """Fixture for dtutil.now."""
    return dt_util.utcnow()


@pytest.fixture(name="mac_address", autouse=True)
def mac_address_fixture() -> Mock:
    """Patch getmac.get_mac_address."""
    with patch("getmac.get_mac_address", return_value=None) as mac:
        yield mac
