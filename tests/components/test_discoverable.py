"""Test discoverable component."""
import time
from unittest.mock import MagicMock, patch

from homeassistant import bootstrap
from homeassistant.components import discoverable, http
from homeassistant.const import __version__

from tests.common import get_test_instance_port, get_test_home_assistant


class TestDiscoverableMethods(object):
    @patch('homeassistant.components.discoverable.AssemblyListener')
    def test_exposing_password_defaults_false(self, mock_listener):
        hass = MagicMock()

        assert discoverable.setup(hass, {})

        assert mock_listener.mock_calls[0][1] == (hass, False)

    def test_exposing_password(self):
        base_url = 'http://very-fancy-host.com:8123'
        api_password = 'secret'

        hass = MagicMock()
        hass.config.api.base_url = base_url
        hass.config.api.api_password = None

        assert discoverable.AssemblyListener(hass, False).response() == {
            'content-type': 'home-assistant/server',
            'host': base_url,
            'version': __version__,
            'api_password': None,
        }

        hass.config.api.api_password = api_password

        assert discoverable.AssemblyListener(hass, False).response() == {
            'content-type': 'home-assistant/server',
            'host': base_url,
            'version': __version__,
        }

        hass.config.api.api_password = api_password

        assert discoverable.AssemblyListener(hass, True).response() == {
            'content-type': 'home-assistant/server',
            'host': base_url,
            'version': __version__,
            'api_password': api_password,
        }


class TestDiscoverableFlow(object):
    def setup_method(self, method):
        self.hass = get_test_home_assistant()
        bootstrap.setup_component(
            self.hass, http.DOMAIN,
            {http.DOMAIN: {http.CONF_API_PASSWORD: 'SuperSecret',
             http.CONF_SERVER_PORT: get_test_instance_port()}})

    def teardown_method(self, method):
        self.hass.stop()

    def test_broadcast_and_get_instance(self):
        self.hass.states.set('test.hello', 'world')

        discoverable.setup(self.hass, {
            discoverable.DOMAIN: {
                discoverable.CONF_EXPOSE_PASSWORD: True
            }
        })

        self.hass.start()

        time.sleep(0.1)

        remote = discoverable.get_instance()

        assert remote is not None
        assert remote.states.is_state('test.hello', 'world')
