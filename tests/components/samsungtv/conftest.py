"""Fixtures for Samsung TV."""
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from samsungctl import Remote
from samsungtvws.async_connection import SamsungTVWSAsyncConnection

import homeassistant.util.dt as dt_util

from .const import SAMPLE_APP_LIST


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
        rest_api_class.return_value.rest_device_info.return_value = {
            "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
            "device": {
                "modelName": "82GXARRS",
                "wifiMac": "aa:bb:cc:dd:ee:ff",
                "name": "[TV] Living Room",
                "type": "Samsung SmartTV",
                "networkType": "wireless",
            },
        }
        yield rest_api_class.return_value


@pytest.fixture(name="remotews")
def remotews_fixture() -> Mock:
    """Patch the samsungtvws SamsungTVWS."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWSAsyncConnection"
    ) as remotews_class:
        remotews = Mock(SamsungTVWSAsyncConnection)
        remotews.__aenter__ = AsyncMock(return_value=remotews)
        remotews.__aexit__ = AsyncMock()
        remotews.connection = AsyncMock()
        remotews.connection.recv.return_value = SAMPLE_APP_LIST
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


@pytest.fixture(name="no_mac_address")
def mac_address_fixture() -> Mock:
    """Patch getmac.get_mac_address."""
    with patch("getmac.get_mac_address", return_value=None) as mac:
        yield mac
