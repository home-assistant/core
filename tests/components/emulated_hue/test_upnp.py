"""The tests for the emulated Hue component."""
import json
import unittest

from aiohttp.hdrs import CONTENT_TYPE
import defusedxml.ElementTree as ET
import requests

from homeassistant import const, setup
from homeassistant.components import emulated_hue
from homeassistant.const import HTTP_OK

from tests.async_mock import patch
from tests.common import get_test_home_assistant, get_test_instance_port

HTTP_SERVER_PORT = get_test_instance_port()
BRIDGE_SERVER_PORT = get_test_instance_port()

BRIDGE_URL_BASE = f"http://127.0.0.1:{BRIDGE_SERVER_PORT}" + "{}"
JSON_HEADERS = {CONTENT_TYPE: const.CONTENT_TYPE_JSON}


class TestEmulatedHue(unittest.TestCase):
    """Test the emulated Hue component."""

    hass = None

    @classmethod
    def setUpClass(cls):
        """Set up the class."""
        cls.hass = hass = get_test_home_assistant()

        with patch("homeassistant.components.emulated_hue.UPNPResponderThread"):
            setup.setup_component(
                hass,
                emulated_hue.DOMAIN,
                {
                    emulated_hue.DOMAIN: {
                        emulated_hue.CONF_LISTEN_PORT: BRIDGE_SERVER_PORT
                    }
                },
            )

        cls.hass.start()

    @classmethod
    def tearDownClass(cls):
        """Stop the class."""
        cls.hass.stop()

    def test_upnp_discovery_basic(self):
        """Tests the UPnP basic discovery response."""
        with patch("threading.Thread.__init__"):
            upnp_responder_thread = emulated_hue.UPNPResponderThread(
                "0.0.0.0", 80, True, "192.0.2.42", 8080
            )

            """Original request emitted by the Hue Bridge v1 app."""
            request = """M-SEARCH * HTTP/1.1
HOST:239.255.255.250:1900
ST:ssdp:all
Man:"ssdp:discover"
MX:3

"""
            encoded_request = request.replace("\n", "\r\n").encode("utf-8")

            response = upnp_responder_thread._handle_request(encoded_request)
            expected_response = """HTTP/1.1 200 OK
CACHE-CONTROL: max-age=60
EXT:
LOCATION: http://192.0.2.42:8080/description.xml
SERVER: FreeRTOS/6.0.5, UPnP/1.0, IpBridge/1.16.0
hue-bridgeid: 001788FFFE23BFC2
ST: urn:schemas-upnp-org:device:basic:1
USN: uuid:2f402f80-da50-11e1-9b23-001788255acc

"""
            assert expected_response.replace("\n", "\r\n").encode("utf-8") == response

    def test_upnp_discovery_rootdevice(self):
        """Tests the UPnP rootdevice discovery response."""
        with patch("threading.Thread.__init__"):
            upnp_responder_thread = emulated_hue.UPNPResponderThread(
                "0.0.0.0", 80, True, "192.0.2.42", 8080
            )

            """Original request emitted by Busch-Jaeger free@home SysAP."""
            request = """M-SEARCH * HTTP/1.1
HOST: 239.255.255.250:1900
MAN: "ssdp:discover"
MX: 40
ST: upnp:rootdevice

"""
            encoded_request = request.replace("\n", "\r\n").encode("utf-8")

            response = upnp_responder_thread._handle_request(encoded_request)
            expected_response = """HTTP/1.1 200 OK
CACHE-CONTROL: max-age=60
EXT:
LOCATION: http://192.0.2.42:8080/description.xml
SERVER: FreeRTOS/6.0.5, UPnP/1.0, IpBridge/1.16.0
hue-bridgeid: 001788FFFE23BFC2
ST: upnp:rootdevice
USN: uuid:2f402f80-da50-11e1-9b23-001788255acc::upnp:rootdevice

"""
            assert expected_response.replace("\n", "\r\n").encode("utf-8") == response

    def test_description_xml(self):
        """Test the description."""
        result = requests.get(BRIDGE_URL_BASE.format("/description.xml"), timeout=5)

        assert result.status_code == HTTP_OK
        assert "text/xml" in result.headers["content-type"]

        # Make sure the XML is parsable
        try:
            root = ET.fromstring(result.text)
            ns = {"s": "urn:schemas-upnp-org:device-1-0"}
            assert root.find("./s:device/s:serialNumber", ns).text == "001788FFFE23BFC2"
        except:  # noqa: E722 pylint: disable=bare-except
            self.fail("description.xml is not valid XML!")

    def test_create_username(self):
        """Test the creation of an username."""
        request_json = {"devicetype": "my_device"}

        result = requests.post(
            BRIDGE_URL_BASE.format("/api"), data=json.dumps(request_json), timeout=5
        )

        assert result.status_code == HTTP_OK
        assert "application/json" in result.headers["content-type"]

        resp_json = result.json()
        success_json = resp_json[0]

        assert "success" in success_json
        assert "username" in success_json["success"]

    def test_unauthorized_view(self):
        """Test unauthorized view."""
        request_json = {"devicetype": "my_device"}

        result = requests.get(
            BRIDGE_URL_BASE.format("/api/unauthorized"),
            data=json.dumps(request_json),
            timeout=5,
        )

        assert result.status_code == HTTP_OK
        assert "application/json" in result.headers["content-type"]

        resp_json = result.json()
        assert len(resp_json) == 1
        success_json = resp_json[0]
        assert len(success_json) == 1

        assert "error" in success_json
        error_json = success_json["error"]
        assert len(error_json) == 3
        assert "/" in error_json["address"]
        assert "unauthorized user" in error_json["description"]
        assert "1" in error_json["type"]

    def test_valid_username_request(self):
        """Test request with a valid username."""
        request_json = {"invalid_key": "my_device"}

        result = requests.post(
            BRIDGE_URL_BASE.format("/api"), data=json.dumps(request_json), timeout=5
        )

        assert result.status_code == 400
