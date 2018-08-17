"""The tests for the MQTT component embedded server."""
from unittest.mock import Mock, MagicMock, patch
import sys

import pytest

from homeassistant.const import CONF_PASSWORD
from homeassistant.setup import setup_component
import homeassistant.components.mqtt as mqtt

from tests.common import get_test_home_assistant, mock_coro


# Until https://github.com/beerfactory/hbmqtt/pull/139 is released
@pytest.mark.skipif(sys.version_info[:2] >= (3, 7),
                    reason='Package incompatible with Python 3.7')
class TestMQTT:
    """Test the MQTT component."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('passlib.apps.custom_app_context', Mock(return_value=''))
    @patch('tempfile.NamedTemporaryFile', Mock(return_value=MagicMock()))
    @patch('hbmqtt.broker.Broker', Mock(return_value=MagicMock()))
    @patch('hbmqtt.broker.Broker.start', Mock(return_value=mock_coro()))
    @patch('homeassistant.components.mqtt.MQTT')
    def test_creating_config_with_http_pass_only(self, mock_mqtt):
        """Test if the MQTT server failed starts.

        Since 0.77, MQTT server has to setup its own password.
        If user has api_password but don't have mqtt.password, MQTT component
         will fail to start
        """
        mock_mqtt().async_connect.return_value = mock_coro(True)
        self.hass.bus.listen_once = MagicMock()
        assert not setup_component(self.hass, mqtt.DOMAIN, {
            'http': {'api_password': 'http_secret'}
        })

    @patch('passlib.apps.custom_app_context', Mock(return_value=''))
    @patch('tempfile.NamedTemporaryFile', Mock(return_value=MagicMock()))
    @patch('hbmqtt.broker.Broker', Mock(return_value=MagicMock()))
    @patch('hbmqtt.broker.Broker.start', Mock(return_value=mock_coro()))
    @patch('homeassistant.components.mqtt.MQTT')
    def test_creating_config_with_pass_and_no_http_pass(self, mock_mqtt):
        """Test if the MQTT server gets started with password.

        Since 0.77, MQTT server has to setup its own password.
        """
        mock_mqtt().async_connect.return_value = mock_coro(True)
        self.hass.bus.listen_once = MagicMock()
        password = 'mqtt_secret'

        assert setup_component(self.hass, mqtt.DOMAIN, {
            mqtt.DOMAIN: {CONF_PASSWORD: password},
        })
        assert mock_mqtt.called
        from pprint import pprint
        pprint(mock_mqtt.mock_calls)
        assert mock_mqtt.mock_calls[1][1][5] == 'homeassistant'
        assert mock_mqtt.mock_calls[1][1][6] == password

    @patch('passlib.apps.custom_app_context', Mock(return_value=''))
    @patch('tempfile.NamedTemporaryFile', Mock(return_value=MagicMock()))
    @patch('hbmqtt.broker.Broker', Mock(return_value=MagicMock()))
    @patch('hbmqtt.broker.Broker.start', Mock(return_value=mock_coro()))
    @patch('homeassistant.components.mqtt.MQTT')
    def test_creating_config_with_pass_and_http_pass(self, mock_mqtt):
        """Test if the MQTT server gets started with password.

        Since 0.77, MQTT server has to setup its own password.
        """
        mock_mqtt().async_connect.return_value = mock_coro(True)
        self.hass.bus.listen_once = MagicMock()
        password = 'mqtt_secret'

        self.hass.config.api = MagicMock(api_password='api_password')
        assert setup_component(self.hass, mqtt.DOMAIN, {
            'http': {'api_password': 'http_secret'},
            mqtt.DOMAIN: {CONF_PASSWORD: password},
        })
        assert mock_mqtt.called
        from pprint import pprint
        pprint(mock_mqtt.mock_calls)
        assert mock_mqtt.mock_calls[1][1][5] == 'homeassistant'
        assert mock_mqtt.mock_calls[1][1][6] == password

    @patch('passlib.apps.custom_app_context', Mock(return_value=''))
    @patch('tempfile.NamedTemporaryFile', Mock(return_value=MagicMock()))
    @patch('hbmqtt.broker.Broker', Mock(return_value=MagicMock()))
    @patch('hbmqtt.broker.Broker.start', Mock(return_value=mock_coro()))
    @patch('homeassistant.components.mqtt.MQTT')
    def test_creating_config_without_pass(self, mock_mqtt):
        """Test if the MQTT server gets started without password."""
        mock_mqtt().async_connect.return_value = mock_coro(True)
        self.hass.bus.listen_once = MagicMock()

        self.hass.config.api = MagicMock(api_password=None)
        assert setup_component(self.hass, mqtt.DOMAIN, {})
        assert mock_mqtt.called
        assert mock_mqtt.mock_calls[1][1][5] is None
        assert mock_mqtt.mock_calls[1][1][6] is None

    @patch('tempfile.NamedTemporaryFile', Mock(return_value=MagicMock()))
    @patch('hbmqtt.broker.Broker.start', return_value=mock_coro())
    def test_broker_config_fails(self, mock_run):
        """Test if the MQTT component fails if server fails."""
        from hbmqtt.broker import BrokerException

        mock_run.side_effect = BrokerException

        self.hass.config.api = MagicMock(api_password=None)

        assert not setup_component(self.hass, mqtt.DOMAIN, {
            mqtt.DOMAIN: {mqtt.CONF_EMBEDDED: {}}
        })
