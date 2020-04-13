"""The tests for the panel_proxy component."""
import unittest

from homeassistant import setup
from homeassistant.components import frontend

from tests.common import get_test_home_assistant


class TestPanelProxy(unittest.TestCase):
    """Test the panel_proxy component."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_wrong_config(self):
        """Test setup with wrong configuration."""
        to_try = [
            {"invalid space": {"url": "https://home-assistant.io"}},
            {"router": {"url": "not-a-url"}},
        ]

        for conf in to_try:
            assert not setup.setup_component(
                self.hass, "panel_proxy", {"panel_proxy": conf}
            )

    def test_correct_config(self):
        """Test correct config."""
        assert setup.setup_component(
            self.hass,
            "panel_proxy",
            {
                "panel_proxy": {
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

        assert panels.get("proxy_router").to_response() == {
            "component_name": "iframe",
            "config": {"url": "/router"},
            "icon": "mdi:network-wireless",
            "title": "Router",
            "url_path": "proxy_router",
            "require_admin": True,
        }

        assert panels.get("proxy_weather").to_response() == {
            "component_name": "iframe",
            "config": {"url": "/weather"},
            "icon": "mdi:weather",
            "title": "Weather",
            "url_path": "proxy_weather",
            "require_admin": True,
        }

        assert panels.get("proxy_api").to_response() == {
            "component_name": "iframe",
            "config": {"url": "/api"},
            "icon": "mdi:weather",
            "title": "Api",
            "url_path": "proxy_api",
            "require_admin": False,
        }

        assert panels.get("proxy_ftp").to_response() == {
            "component_name": "iframe",
            "config": {"url": "/ftp"},
            "icon": "mdi:weather",
            "title": "FTP",
            "url_path": "proxy_ftp",
            "require_admin": False,
        }
