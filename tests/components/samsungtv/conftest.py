"""Fixtures for Samsung TV."""
from unittest.mock import Mock, patch

import pytest

import homeassistant.util.dt as dt_util

RESULT_ALREADY_CONFIGURED = "already_configured"
RESULT_ALREADY_IN_PROGRESS = "already_in_progress"


@pytest.fixture(name="remote")
def remote_fixture():
    """Patch the samsungctl Remote."""
    with patch(
        "homeassistant.components.samsungtv.bridge.Remote"
    ) as remote_class, patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
        remote = Mock()
        remote.__enter__ = Mock()
        remote.__exit__ = Mock()
        remote.port.return_value = 55000
        remote_class.return_value = remote
        yield remote


@pytest.fixture(name="remotews")
def remotews_fixture():
    """Patch the samsungtvws SamsungTVWS."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS"
    ) as remotews_class, patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
        remotews = Mock()
        remotews.__enter__ = Mock()
        remotews.__exit__ = Mock()
        remotews.port.return_value = 8002
        remotews.rest_device_info.return_value = {
            "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
            "device": {
                "modelName": "82GXARRS",
                "wifiMac": "aa:bb:cc:dd:ee:ff",
                "name": "[TV] Living Room",
                "type": "Samsung SmartTV",
                "networkType": "wireless",
            },
        }
        remotews_class.return_value = remotews
        remotews_class().__enter__().token = "FAKE_TOKEN"
        yield remotews


@pytest.fixture(name="remotews_no_device_info")
def remotews_no_device_info_fixture():
    """Patch the samsungtvws SamsungTVWS."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS"
    ) as remotews_class, patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
        remotews = Mock()
        remotews.__enter__ = Mock()
        remotews.__exit__ = Mock()
        remotews.rest_device_info.return_value = None
        remotews_class.return_value = remotews
        remotews_class().__enter__().token = "FAKE_TOKEN"
        yield remotews


@pytest.fixture(name="remotews_soundbar")
def remotews_soundbar_fixture():
    """Patch the samsungtvws SamsungTVWS."""
    with patch(
        "homeassistant.components.samsungtv.bridge.SamsungTVWS"
    ) as remotews_class, patch(
        "homeassistant.components.samsungtv.config_flow.socket.gethostbyname",
        return_value="fake_host",
    ):
        remotews = Mock()
        remotews.__enter__ = Mock()
        remotews.__exit__ = Mock()
        remotews.rest_device_info.return_value = {
            "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
            "device": {
                "modelName": "82GXARRS",
                "wifiMac": "aa:bb:cc:dd:ee:ff",
                "mac": "aa:bb:cc:dd:ee:ff",
                "name": "[TV] Living Room",
                "type": "Samsung SoundBar",
            },
        }
        remotews_class.return_value = remotews
        remotews_class().__enter__().token = "FAKE_TOKEN"
        yield remotews


@pytest.fixture(name="delay")
def delay_fixture():
    """Patch the delay script function."""
    with patch(
        "homeassistant.components.samsungtv.media_player.Script.async_run"
    ) as delay:
        yield delay


@pytest.fixture
def mock_now():
    """Fixture for dtutil.now."""
    return dt_util.utcnow()


@pytest.fixture(name="no_mac_address")
def mac_address_fixture():
    """Patch getmac.get_mac_address."""
    with patch("getmac.get_mac_address", return_value=None) as mac:
        yield mac
