"""The tests for the Ring component."""
from asyncio import run_coroutine_threadsafe
from datetime import timedelta
import unittest

import requests_mock

import homeassistant.components.ring as ring

from tests.common import get_test_home_assistant, load_fixture

ATTRIBUTION = "Data provided by Ring.com"

VALID_CONFIG = {
    "ring": {"username": "foo", "password": "bar", "scan_interval": timedelta(10)}
}


class TestRing(unittest.TestCase):
    """Tests the Ring component."""

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup(self, mock):
        """Test the setup."""
        mock.post(
            "https://oauth.ring.com/oauth/token", text=load_fixture("ring_oauth.json")
        )
        mock.post(
            "https://api.ring.com/clients_api/session",
            text=load_fixture("ring_session.json"),
        )
        mock.get(
            "https://api.ring.com/clients_api/ring_devices",
            text=load_fixture("ring_devices.json"),
        )
        mock.get(
            "https://api.ring.com/clients_api/chimes/999999/health",
            text=load_fixture("ring_chime_health_attrs.json"),
        )
        mock.get(
            "https://api.ring.com/clients_api/doorbots/987652/health",
            text=load_fixture("ring_doorboot_health_attrs.json"),
        )
        response = run_coroutine_threadsafe(
            ring.async_setup(self.hass, self.config), self.hass.loop
        ).result()

        assert response
