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
