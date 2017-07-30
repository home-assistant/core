"""The tests for the MQTT component embedded server."""
from unittest.mock import Mock, MagicMock, patch

from homeassistant.setup import setup_component
import homeassistant.components.mqtt as mqtt

from tests.common import (
    get_test_home_assistant, mock_coro, mock_http_component)


class TestMQTT:
    """Test the MQTT component."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_http_component(self.hass, 'super_secret')

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('passlib.apps.custom_app_context', Mock(return_value=''))
    @patch('tempfile.NamedTemporaryFile', Mock(return_value=MagicMock()))
    @patch('hbmqtt.broker.Broker', Mock(return_value=MagicMock()))
    @patch('hbmqtt.broker.Broker.start', Mock(return_value=mock_coro()))
    @patch('homeassistant.components.mqtt.MQTT')
    def test_creating_config_with_http_pass(self, mock_mqtt):
        """Test if the MQTT server gets started and subscribe/publish msg."""
        mock_mqtt().async_connect.return_value = mock_coro(True)
        self.hass.bus.listen_once = MagicMock()
        password = 'super_secret'

        self.hass.config.api = MagicMock(api_password=password)
        assert setup_component(self.hass, mqtt.DOMAIN, {})
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
    def test_creating_config_with_http_no_pass(self, mock_mqtt):
        """Test if the MQTT server gets started and subscribe/publish msg."""
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
