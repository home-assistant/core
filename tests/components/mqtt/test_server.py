"""The tests for the MQTT component embedded server."""
from unittest.mock import MagicMock, patch

from homeassistant.bootstrap import _setup_component
import homeassistant.components.mqtt as mqtt

from tests.common import get_test_home_assistant


class TestMQTT:
    """Test the MQTT component."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('homeassistant.components.mqtt.MQTT')
    @patch('asyncio.gather')
    @patch('asyncio.new_event_loop')
    def test_creating_config_with_http_pass(self, mock_new_loop, mock_gather,
                                            mock_mqtt):
        """Test if the MQTT server gets started and subscribe/publish msg."""
        self.hass.config.components.append('http')
        password = 'super_secret'

        self.hass.config.api = MagicMock(api_password=password)
        assert _setup_component(self.hass, mqtt.DOMAIN, {})
        assert mock_mqtt.called
        assert mock_mqtt.mock_calls[0][1][5] == 'homeassistant'
        assert mock_mqtt.mock_calls[0][1][6] == password

        mock_mqtt.reset_mock()

        self.hass.config.components = ['http']
        self.hass.config.api = MagicMock(api_password=None)
        assert _setup_component(self.hass, mqtt.DOMAIN, {})
        assert mock_mqtt.called
        assert mock_mqtt.mock_calls[0][1][5] is None
        assert mock_mqtt.mock_calls[0][1][6] is None

    @patch('asyncio.gather')
    @patch('asyncio.new_event_loop')
    def test_broker_config_fails(self, mock_new_loop, mock_gather):
        """Test if the MQTT component fails if server fails."""
        self.hass.config.components.append('http')
        from hbmqtt.broker import BrokerException

        mock_gather.side_effect = BrokerException

        self.hass.config.api = MagicMock(api_password=None)
        assert not _setup_component(self.hass, mqtt.DOMAIN, {
            mqtt.DOMAIN: {mqtt.CONF_EMBEDDED: {}}
        })
