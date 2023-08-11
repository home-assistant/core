"""The tests for the Xiaomi router device tracker platform."""
from http import HTTPStatus
import logging
from unittest.mock import MagicMock, call, patch

import requests

from homeassistant.components.device_tracker import DOMAIN
import homeassistant.components.xiaomi.device_tracker as xiaomi
from homeassistant.components.xiaomi.device_tracker import get_scanner
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PLATFORM, CONF_USERNAME
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

INVALID_USERNAME = "bob"
TOKEN_TIMEOUT_USERNAME = "tok"
URL_AUTHORIZE = "http://192.168.0.1/cgi-bin/luci/api/xqsystem/login"
URL_LIST_END = "api/misystem/devicelist"

FIRST_CALL = True


def mocked_requests(*args, **kwargs):
    """Mock requests.get invocations."""

    class MockResponse:
        """Class to represent a mocked response."""

        def __init__(self, json_data, status_code):
            """Initialize the mock response class."""
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            """Return the json of the response."""
            return self.json_data

        @property
        def content(self):
            """Return the content of the response."""
            return self.json()

        def raise_for_status(self):
            """Raise an HTTPError if status is not OK."""
            if self.status_code != HTTPStatus.OK:
                raise requests.HTTPError(self.status_code)

    data = kwargs.get("data")
    global FIRST_CALL

    if data and data.get("username", None) == INVALID_USERNAME:
        # deliver an invalid token
        return MockResponse({"code": "401", "msg": "Invalid token"}, 200)
    if data and data.get("username", None) == TOKEN_TIMEOUT_USERNAME:
        # deliver an expired token
        return MockResponse(
            {
                "url": "/cgi-bin/luci/;stok=ef5860/web/home",
                "token": "timedOut",
                "code": "0",
            },
            200,
        )
    if str(args[0]).startswith(URL_AUTHORIZE):
        # deliver an authorized token
        return MockResponse(
            {
                "url": "/cgi-bin/luci/;stok=ef5860/web/home",
                "token": "ef5860",
                "code": "0",
            },
            200,
        )
    if str(args[0]).endswith(f"timedOut/{URL_LIST_END}") and FIRST_CALL is True:
        FIRST_CALL = False
        # deliver an error when called with expired token
        return MockResponse({"code": "401", "msg": "Invalid token"}, 200)
    if str(args[0]).endswith(URL_LIST_END):
        # deliver the device list
        return MockResponse(
            {
                "mac": "1C:98:EC:0E:D5:A4",
                "list": [
                    {
                        "mac": "23:83:BF:F6:38:A0",
                        "oname": "12255ff",
                        "isap": 0,
                        "parent": "",
                        "authority": {"wan": 1, "pridisk": 0, "admin": 1, "lan": 0},
                        "push": 0,
                        "online": 1,
                        "name": "Device1",
                        "times": 0,
                        "ip": [
                            {
                                "downspeed": "0",
                                "online": "496957",
                                "active": 1,
                                "upspeed": "0",
                                "ip": "192.168.0.25",
                            }
                        ],
                        "statistics": {
                            "downspeed": "0",
                            "online": "496957",
                            "upspeed": "0",
                        },
                        "icon": "",
                        "type": 1,
                    },
                    {
                        "mac": "1D:98:EC:5E:D5:A6",
                        "oname": "CdddFG58",
                        "isap": 0,
                        "parent": "",
                        "authority": {"wan": 1, "pridisk": 0, "admin": 1, "lan": 0},
                        "push": 0,
                        "online": 1,
                        "name": "Device2",
                        "times": 0,
                        "ip": [
                            {
                                "downspeed": "0",
                                "online": "347325",
                                "active": 1,
                                "upspeed": "0",
                                "ip": "192.168.0.3",
                            }
                        ],
                        "statistics": {
                            "downspeed": "0",
                            "online": "347325",
                            "upspeed": "0",
                        },
                        "icon": "",
                        "type": 0,
                    },
                ],
                "code": 0,
            },
            200,
        )
    _LOGGER.debug("UNKNOWN ROUTE")


@patch(
    "homeassistant.components.xiaomi.device_tracker.XiaomiDeviceScanner",
    return_value=MagicMock(),
)
async def test_config(xiaomi_mock, hass: HomeAssistant) -> None:
    """Testing minimal configuration."""
    config = {
        DOMAIN: xiaomi.PLATFORM_SCHEMA(
            {
                CONF_PLATFORM: xiaomi.DOMAIN,
                CONF_HOST: "192.168.0.1",
                CONF_PASSWORD: "passwordTest",
            }
        )
    }
    xiaomi.get_scanner(hass, config)
    assert xiaomi_mock.call_count == 1
    assert xiaomi_mock.call_args == call(config[DOMAIN])
    call_arg = xiaomi_mock.call_args[0][0]
    assert call_arg["username"] == "admin"
    assert call_arg["password"] == "passwordTest"
    assert call_arg["host"] == "192.168.0.1"
    assert call_arg["platform"] == "device_tracker"


@patch(
    "homeassistant.components.xiaomi.device_tracker.XiaomiDeviceScanner",
    return_value=MagicMock(),
)
async def test_config_full(xiaomi_mock, hass: HomeAssistant) -> None:
    """Testing full configuration."""
    config = {
        DOMAIN: xiaomi.PLATFORM_SCHEMA(
            {
                CONF_PLATFORM: xiaomi.DOMAIN,
                CONF_HOST: "192.168.0.1",
                CONF_USERNAME: "alternativeAdminName",
                CONF_PASSWORD: "passwordTest",
            }
        )
    }
    xiaomi.get_scanner(hass, config)
    assert xiaomi_mock.call_count == 1
    assert xiaomi_mock.call_args == call(config[DOMAIN])
    call_arg = xiaomi_mock.call_args[0][0]
    assert call_arg["username"] == "alternativeAdminName"
    assert call_arg["password"] == "passwordTest"
    assert call_arg["host"] == "192.168.0.1"
    assert call_arg["platform"] == "device_tracker"


@patch("requests.get", side_effect=mocked_requests)
@patch("requests.post", side_effect=mocked_requests)
async def test_invalid_credential(mock_get, mock_post, hass: HomeAssistant) -> None:
    """Testing invalid credential handling."""
    config = {
        DOMAIN: xiaomi.PLATFORM_SCHEMA(
            {
                CONF_PLATFORM: xiaomi.DOMAIN,
                CONF_HOST: "192.168.0.1",
                CONF_USERNAME: INVALID_USERNAME,
                CONF_PASSWORD: "passwordTest",
            }
        )
    }
    assert get_scanner(hass, config) is None


@patch("requests.get", side_effect=mocked_requests)
@patch("requests.post", side_effect=mocked_requests)
async def test_valid_credential(mock_get, mock_post, hass: HomeAssistant) -> None:
    """Testing valid refresh."""
    config = {
        DOMAIN: xiaomi.PLATFORM_SCHEMA(
            {
                CONF_PLATFORM: xiaomi.DOMAIN,
                CONF_HOST: "192.168.0.1",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "passwordTest",
            }
        )
    }
    scanner = get_scanner(hass, config)
    assert scanner is not None
    assert len(scanner.scan_devices()) == 2
    assert scanner.get_device_name("23:83:BF:F6:38:A0") == "Device1"
    assert scanner.get_device_name("1D:98:EC:5E:D5:A6") == "Device2"


@patch("requests.get", side_effect=mocked_requests)
@patch("requests.post", side_effect=mocked_requests)
async def test_token_timed_out(mock_get, mock_post, hass: HomeAssistant) -> None:
    """Testing refresh with a timed out token.

    New token is requested and list is downloaded a second time.
    """
    config = {
        DOMAIN: xiaomi.PLATFORM_SCHEMA(
            {
                CONF_PLATFORM: xiaomi.DOMAIN,
                CONF_HOST: "192.168.0.1",
                CONF_USERNAME: TOKEN_TIMEOUT_USERNAME,
                CONF_PASSWORD: "passwordTest",
            }
        )
    }
    scanner = get_scanner(hass, config)
    assert scanner is not None
    assert len(scanner.scan_devices()) == 2
    assert scanner.get_device_name("23:83:BF:F6:38:A0") == "Device1"
    assert scanner.get_device_name("1D:98:EC:5E:D5:A6") == "Device2"
