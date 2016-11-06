"""The tests for the Prometheus exporter."""
import unittest

import requests

from homeassistant import bootstrap, const
import homeassistant.core as ha
import homeassistant.components.prometheus as prometheus
import homeassistant.components.http as http

from tests.common import get_test_instance_port, get_test_home_assistant

API_PASSWORD = "test1234"
SERVER_PORT = get_test_instance_port()
PROMETHEUS_URL = "http://127.0.0.1:{}/api/prometheus".format(SERVER_PORT)
HA_HEADERS = {
    const.HTTP_HEADER_HA_AUTH: API_PASSWORD,
}

hass = None


# pylint: disable=invalid-name
def setUpModule():
    """Initialize a Home Assistant server."""
    global hass

    hass = get_test_home_assistant()

    assert bootstrap.setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
                       http.CONF_SERVER_PORT: SERVER_PORT}})

    assert bootstrap.setup_component(hass, 'api')

    assert bootstrap.setup_component(hass, 'prometheus')

    hass.start()


# pylint: disable=invalid-name
def tearDownModule():
    """Stop everything that was started."""
    hass.stop()


class TestPrometheus(unittest.TestCase):
    """Test the Prometheus component."""

    def test_view(self):
        """Test prometheus metrics view."""
        req = requests.get(PROMETHEUS_URL, headers=HA_HEADERS)
        self.assertEqual(req.headers['content-type'], 'text/plain')
        for line in req.text.split("\n"):
            if line:
                self.assertTrue(
                    line.startswith('# ') or line.startswith('process_'),
                )
