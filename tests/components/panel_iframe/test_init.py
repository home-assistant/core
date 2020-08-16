"""The tests for the panel_iframe component."""
import unittest

from homeassistant import setup
from homeassistant.components import frontend

from tests.async_mock import patch
from tests.common import get_test_home_assistant


class TestPanelIframe(unittest.TestCase):
    """Test the panel_iframe component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.hass.stop)

    def test_wrong_config(self):
        """Test setup with wrong configuration."""
        to_try = [
            {"invalid space": {"url": "https://home-assistant.io"}},
            {"router": {"url": "not-a-url"}},
        ]

        for conf in to_try:
            with patch(
                "homeassistant.components.http.start_http_server_and_save_config"
            ):
                assert not setup.setup_component(
                    self.hass, "panel_iframe", {"panel_iframe": conf}
                )

    def test_correct_config(self):
        """Test correct config."""
        with patch("homeassistant.components.http.start_http_server_and_save_config"):
            assert setup.setup_component(
                self.hass,
                "panel_iframe",
                {
                    "panel_iframe": {
                        "router": {
                            "icon": "mdi:network-wireless",
                            "title": "Router",
                            "url": "http://192.168.1.1",
                            "require_admin": True,
                        },
                        "weather": {
                            "icon": "mdi:weather",
                            "title": "Weather",
                            "url": "https://www.wunderground.com/us/ca/san-diego",
                            "require_admin": True,
                        },
                        "api": {"icon": "mdi:weather", "title": "Api", "url": "/api"},
                        "ftp": {
                            "icon": "mdi:weather",
                            "title": "FTP",
                            "url": "ftp://some/ftp",
                        },
                    }
                },
            )

        panels = self.hass.data[frontend.DATA_PANELS]

        assert panels.get("router").to_response() == {
            "component_name": "iframe",
            "config": {"url": "http://192.168.1.1"},
            "icon": "mdi:network-wireless",
            "title": "Router",
            "url_path": "router",
            "require_admin": True,
        }

        assert panels.get("weather").to_response() == {
            "component_name": "iframe",
            "config": {"url": "https://www.wunderground.com/us/ca/san-diego"},
            "icon": "mdi:weather",
            "title": "Weather",
            "url_path": "weather",
            "require_admin": True,
        }

        assert panels.get("api").to_response() == {
            "component_name": "iframe",
            "config": {"url": "/api"},
            "icon": "mdi:weather",
            "title": "Api",
            "url_path": "api",
            "require_admin": False,
        }

        assert panels.get("ftp").to_response() == {
            "component_name": "iframe",
            "config": {"url": "ftp://some/ftp"},
            "icon": "mdi:weather",
            "title": "FTP",
            "url_path": "ftp",
            "require_admin": False,
        }
