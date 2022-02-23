"""Fixtures for Samsung TV."""
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from samsungctl import Remote
from samsungtvws import SamsungTVWS
from samsungtvws.async_rest import SamsungTVAsyncRest

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


@pytest.fixture(name="remotews")
def remotews_fixture() -> Mock:
    """Patch the samsungtvws SamsungTVWS."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS"
    ) as remotews_class, patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVAsyncRest"
    ) as rest_api_class:
        rest_api = Mock(SamsungTVAsyncRest)
        remotews = Mock(SamsungTVWS)
        remotews.__enter__ = Mock(return_value=remotews)
        remotews.__exit__ = Mock()
        rest_api.rest_device_info.return_value = {
            "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
            "device": {
                "modelName": "82GXARRS",
                "wifiMac": "aa:bb:cc:dd:ee:ff",
                "name": "[TV] Living Room",
                "type": "Samsung SmartTV",
                "networkType": "wireless",
            },
        }
        remotews.app_list.return_value = SAMPLE_APP_LIST
        remotews.token = "FAKE_TOKEN"
        rest_api_class.return_value = rest_api
        remotews_class.return_value = remotews
        yield remotews


@pytest.fixture(name="remotews_no_device_info")
def remotews_no_device_info_fixture() -> Mock:
    """Patch the samsungtvws SamsungTVWS."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS"
    ) as remotews_class, patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVAsyncRest"
    ) as rest_api_class:
        rest_api = Mock(SamsungTVAsyncRest)
        remotews = Mock(SamsungTVWS)
        remotews.__enter__ = Mock(return_value=remotews)
        remotews.__exit__ = Mock()
        rest_api.rest_device_info.return_value = None
        remotews.token = "FAKE_TOKEN"
        rest_api_class.return_value = rest_api
        remotews_class.return_value = remotews
        yield remotews


@pytest.fixture(name="remotews_soundbar")
def remotews_soundbar_fixture() -> Mock:
    """Patch the samsungtvws SamsungTVWS."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS"
    ) as remotews_class, patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVAsyncRest"
    ) as rest_api_class:
        rest_api = Mock(SamsungTVAsyncRest)
        remotews = Mock(SamsungTVWS)
        remotews.__enter__ = Mock(return_value=remotews)
        remotews.__exit__ = Mock()
        rest_api.rest_device_info.return_value = {
            "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
            "device": {
                "modelName": "82GXARRS",
                "wifiMac": "aa:bb:cc:dd:ee:ff",
                "mac": "aa:bb:cc:dd:ee:ff",
                "name": "[TV] Living Room",
                "type": "Samsung SoundBar",
            },
        }
        remotews.token = "FAKE_TOKEN"
        rest_api_class.return_value = rest_api
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
