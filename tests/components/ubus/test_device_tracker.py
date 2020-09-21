"""Tests for the ubus device tracker."""
import json
import logging
from typing import List, Optional

from homeassistant.components.device_tracker import DOMAIN
import homeassistant.components.ubus.device_tracker as ubus
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PLATFORM, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.async_mock import MagicMock, call, patch

_LOGGER = logging.getLogger(__name__)

VALID_USERNAME = "alice"
INVALID_USERNAME = "bob"
TIMEOUT_USERNAME = "timeout"
PASSWORD = "PasswordTest"
SESSION = "testSession"
SESSION_TIMEOUT = "SessionTimeout"
HOST = "192.168.0.1"
MAC_DEVICE_1 = "11:22:33:44:55:66"
MAC_DEVICE_2 = "66:55:44:33:22:11"
MAC_DEVICE_3 = "66:55:44:11:22:33"

CONF_DHCP_NONE = "none"
CONF_DHCP_DNSMASQ = "dnsmasq"
CONF_DHCP_ODHCPD = "odhcpd"

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

    global FIRST_CALL
    request = json.loads(kwargs.get("data"))
    request_params = request["params"]

    # Parsing request data like the parameter of _req_json_rpc
    rpcmethod = request["method"]
    session_id = request_params[0]
    subsystem = request_params[1]
    method = request_params[2]
    params = request_params[3]

    if session_id == SESSION_TIMEOUT and FIRST_CALL:
        FIRST_CALL = False
        return MockResponse(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32002, "message": "Access denied"},
            },
            200,
        )

    if rpcmethod == "list" and subsystem == "hostapd.*":
        return MockResponse(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "hostapd.wlan0": {
                        "get_clients": {},
                        "del_client": {
                            "addr": "string",
                            "reason": "number",
                            "deauth": "boolean",
                            "ban_time": "number",
                        },
                        "list_bans": {},
                        "wps_start": {},
                        "wps_cancel": {},
                        "update_beacon": {},
                        "get_features": {},
                        "switch_chan": {
                            "freq": "number",
                            "bcn_count": "number",
                            "center_freq1": "number",
                            "center_freq2": "number",
                            "bandwidth": "number",
                            "sec_channel_offset": "number",
                            "ht": "boolean",
                            "vht": "boolean",
                            "block_tx": "boolean",
                        },
                        "set_vendor_elements": {"vendor_elements": "string"},
                        "notify_response": {"notify_response": "number"},
                        "bss_mgmt_enable": {
                            "neighbor_report": "boolean",
                            "beacon_report": "boolean",
                        },
                        "rrm_nr_get_own": {},
                        "rrm_nr_list": {},
                        "rrm_nr_set": {"list": "array"},
                        "rrm_beacon_req": {
                            "addr": "string",
                            "mode": "number",
                            "op_class": "number",
                            "channel": "number",
                            "duration": "number",
                            "bssid": "string",
                            "ssid": "string",
                        },
                    },
                    "hostapd.wlan0-1": {
                        "get_clients": {},
                        "del_client": {
                            "addr": "string",
                            "reason": "number",
                            "deauth": "boolean",
                            "ban_time": "number",
                        },
                        "list_bans": {},
                        "wps_start": {},
                        "wps_cancel": {},
                        "update_beacon": {},
                        "get_features": {},
                        "switch_chan": {
                            "freq": "number",
                            "bcn_count": "number",
                            "center_freq1": "number",
                            "center_freq2": "number",
                            "bandwidth": "number",
                            "sec_channel_offset": "number",
                            "ht": "boolean",
                            "vht": "boolean",
                            "block_tx": "boolean",
                        },
                        "set_vendor_elements": {"vendor_elements": "string"},
                        "notify_response": {"notify_response": "number"},
                        "bss_mgmt_enable": {
                            "neighbor_report": "boolean",
                            "beacon_report": "boolean",
                        },
                        "rrm_nr_get_own": {},
                        "rrm_nr_list": {},
                        "rrm_nr_set": {"list": "array"},
                        "rrm_beacon_req": {
                            "addr": "string",
                            "mode": "number",
                            "op_class": "number",
                            "channel": "number",
                            "duration": "number",
                            "bssid": "string",
                            "ssid": "string",
                        },
                    },
                    "hostapd.wlan1": {
                        "get_clients": {},
                        "del_client": {
                            "addr": "string",
                            "reason": "number",
                            "deauth": "boolean",
                            "ban_time": "number",
                        },
                        "list_bans": {},
                        "wps_start": {},
                        "wps_cancel": {},
                        "update_beacon": {},
                        "get_features": {},
                        "switch_chan": {
                            "freq": "number",
                            "bcn_count": "number",
                            "center_freq1": "number",
                            "center_freq2": "number",
                            "bandwidth": "number",
                            "sec_channel_offset": "number",
                            "ht": "boolean",
                            "vht": "boolean",
                            "block_tx": "boolean",
                        },
                        "set_vendor_elements": {"vendor_elements": "string"},
                        "notify_response": {"notify_response": "number"},
                        "bss_mgmt_enable": {
                            "neighbor_report": "boolean",
                            "beacon_report": "boolean",
                        },
                        "rrm_nr_get_own": {},
                        "rrm_nr_list": {},
                        "rrm_nr_set": {"list": "array"},
                        "rrm_beacon_req": {
                            "addr": "string",
                            "mode": "number",
                            "op_class": "number",
                            "channel": "number",
                            "duration": "number",
                            "bssid": "string",
                            "ssid": "string",
                        },
                    },
                },
            },
            200,
        )
    elif rpcmethod == "call":
        if subsystem == "iwinfo" and method == "info":
            return MockResponse(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": [
                        0,
                        {
                            "phy": "phy0",
                            "ssid": "Test" + params["device"],
                            "bssid": "AB:CD:EF:12:34:56",
                            "country": "IT",
                            "mode": "Master",
                            "channel": 36,
                            "frequency": 5180,
                            "frequency_offset": 0,
                            "txpower": 23,
                            "txpower_offset": 0,
                            "quality": 65,
                            "quality_max": 70,
                            "signal": -45,
                            "noise": -102,
                            "bitrate": 866700,
                            "encryption": {
                                "enabled": True,
                                "wpa": [2],
                                "authentication": ["psk"],
                                "ciphers": ["ccmp"],
                            },
                            "htmodes": ["HT20", "HT40", "VHT20", "VHT40", "VHT80"],
                            "hwmodes": ["ac", "n"],
                            "hardware": {"id": [1, 2, 3, 4], "name": "Test Hardware"},
                        },
                    ],
                },
                200,
            )
        elif "hostapd." in subsystem and method == "get_clients":
            if "wlan0-1" in subsystem:
                return MockResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "result": [
                            0,
                            {
                                "freq": 5180,
                                "clients": {
                                    MAC_DEVICE_2: {
                                        "auth": True,
                                        "assoc": True,
                                        "authorized": True,
                                        "preauth": False,
                                        "wds": False,
                                        "wmm": True,
                                        "ht": True,
                                        "vht": False,
                                        "wps": False,
                                        "mfp": False,
                                        "rrm": [0, 0, 0, 0, 0],
                                        "aid": 3,
                                    },
                                    MAC_DEVICE_3: {
                                        "auth": True,
                                        "assoc": True,
                                        "authorized": True,
                                        "preauth": False,
                                        "wds": False,
                                        "wmm": True,
                                        "ht": True,
                                        "vht": False,
                                        "wps": False,
                                        "mfp": False,
                                        "rrm": [0, 0, 0, 0, 0],
                                        "aid": 2,
                                    },
                                },
                            },
                        ],
                    },
                    200,
                )
            elif "wlan0" in subsystem:
                return MockResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "result": [
                            0,
                            {
                                "freq": 5180,
                                "clients": {
                                    MAC_DEVICE_1: {
                                        "auth": True,
                                        "assoc": True,
                                        "authorized": True,
                                        "preauth": False,
                                        "wds": False,
                                        "wmm": True,
                                        "ht": True,
                                        "vht": True,
                                        "wps": False,
                                        "mfp": False,
                                        "rrm": [0, 0, 0, 0, 0],
                                        "aid": 2,
                                    }
                                },
                            },
                        ],
                    },
                    200,
                )
            elif "wlan1" in subsystem:
                return MockResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "result": [0, {"freq": 2462, "clients": {}}],
                    },
                    200,
                )
        elif subsystem == "session" and method == "login":
            if params["username"] in [VALID_USERNAME, TIMEOUT_USERNAME]:
                session = (
                    SESSION if params["username"] == VALID_USERNAME else SESSION_TIMEOUT
                )
                return MockResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "result": [
                            0,
                            {
                                "ubus_rpc_session": session,
                                "timeout": 300,
                                "expires": 299,
                                "acls": {
                                    "access-group": {"home-assistant": ["read"]},
                                    "ubus": {
                                        "hostapd.*": ["get_clients"],
                                        "iwinfo": ["devices", "info"],
                                    },
                                },
                                "data": {"username": "home-assistant"},
                            },
                        ],
                    },
                    200,
                )
            elif params["username"] == INVALID_USERNAME:
                return MockResponse({"jsonrpc": "2.0", "id": 1, "result": [6]}, 200)

    raise NotImplementedError


def assert_device(scanner: ubus.UbusDeviceScanner, devices: List[str], device: str):
    """Assert that the device is in the devices and has the correct extra attributes."""
    ssid = "Testwlan0" if device == MAC_DEVICE_1 else "Testwlan0-1"
    assert device in devices
    assert scanner.get_extra_attributes(device) == {"ssid": ssid, "host": HOST}
    assert scanner.get_device_name(device) is None


def get_config(username: str = VALID_USERNAME, dhcp_software: Optional[str] = None):
    """Return the ubus config."""
    config = {
        DOMAIN: ubus.PLATFORM_SCHEMA(
            {
                CONF_PLATFORM: ubus.DOMAIN,
                CONF_HOST: HOST,
                CONF_USERNAME: username,
                CONF_PASSWORD: PASSWORD,
            }
        )
    }
    if dhcp_software is not None:
        config[DOMAIN][ubus.CONF_DHCP_SOFTWARE] = dhcp_software

    return config


async def valid_dhcp_none(hass, username: str):
    """Test the config without dhcp support with the given username."""
    config = get_config(username, CONF_DHCP_NONE)

    scanner = ubus.get_scanner(hass, config)
    assert isinstance(scanner, ubus.UbusDeviceScanner)
    devices = scanner.scan_devices()
    assert 3 == len(devices)
    assert_device(scanner, devices, MAC_DEVICE_1)
    assert_device(scanner, devices, MAC_DEVICE_2)
    assert_device(scanner, devices, MAC_DEVICE_3)

    # not existing device
    assert scanner.get_extra_attributes("ff:ff:ff:ff:ff:ff") is None


@patch("requests.post", side_effect=mocked_requests)
async def test_dhcp_none_valid(mock: MagicMock, hass: HomeAssistant):
    """Testing valid UbusDeviceScanner."""
    await valid_dhcp_none(hass, VALID_USERNAME)


@patch("requests.post", side_effect=mocked_requests)
async def test_dhcp_none_session_timed_out(mock: MagicMock, hass: HomeAssistant):
    """Testing UbusDeviceScanner with a timed out session.

    New session is requested and list is downloaded a second time.
    """
    await valid_dhcp_none(hass, TIMEOUT_USERNAME)


@patch("requests.post", side_effect=mocked_requests)
async def test_dhcp_none_invalid_credentials(mock: MagicMock, hass: HomeAssistant):
    """Testing invalid credentials."""
    config = get_config(INVALID_USERNAME, CONF_DHCP_NONE)
    scanner = ubus.get_scanner(hass, config)
    assert scanner is None


async def verify_config(ubus_mock: MagicMock, hass: HomeAssistant, config: dict):
    """Verify that the mock was called with the correct parameters."""
    ubus.get_scanner(hass, config)
    assert ubus_mock.call_count == 1
    assert ubus_mock.call_args == call(config[DOMAIN])
    call_arg = ubus_mock.call_args[0][0]
    assert call_arg["username"] == VALID_USERNAME
    assert call_arg["password"] == PASSWORD
    assert call_arg["host"] == HOST
    assert call_arg["platform"] == ubus.DOMAIN


@patch(
    "homeassistant.components.ubus.device_tracker.UbusDeviceScanner",
    return_value=MagicMock(),
)
async def test_config_dhcp_none(ubus_mock: MagicMock, hass: HomeAssistant):
    """Testing configuration without dhcp."""
    config = get_config(VALID_USERNAME, CONF_DHCP_NONE)
    await verify_config(ubus_mock, hass, config)


@patch(
    "homeassistant.components.ubus.device_tracker.DnsmasqUbusDeviceScanner",
    return_value=MagicMock(),
)
async def test_config_dhcp_dnsmasq(ubus_mock: MagicMock, hass: HomeAssistant):
    """Testing dnsmasq configuration."""
    config = get_config(VALID_USERNAME)
    await verify_config(ubus_mock, hass, config)


@patch(
    "homeassistant.components.ubus.device_tracker.DnsmasqUbusDeviceScanner",
    return_value=MagicMock(),
)
async def test_config_dhcp_dnsmasq_full(ubus_mock: MagicMock, hass: HomeAssistant):
    """Testing full dnsmasq configuration."""
    config = get_config(VALID_USERNAME, CONF_DHCP_DNSMASQ)
    await verify_config(ubus_mock, hass, config)


@patch(
    "homeassistant.components.ubus.device_tracker.OdhcpdUbusDeviceScanner",
    return_value=MagicMock(),
)
async def test_config_dhcp_odhcpd(ubus_mock: MagicMock, hass: HomeAssistant):
    """Testing odhcpd configuration."""
    config = get_config(VALID_USERNAME, CONF_DHCP_ODHCPD)
    await verify_config(ubus_mock, hass, config)
