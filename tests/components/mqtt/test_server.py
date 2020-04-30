"""The tests for the MQTT component embedded server."""
from unittest.mock import MagicMock, Mock

import pytest

import homeassistant.components.mqtt as mqtt
from homeassistant.const import CONF_PASSWORD
from homeassistant.setup import setup_component

from tests.async_mock import AsyncMock, patch
from tests.common import get_test_home_assistant, mock_coro


@pytest.fixture(autouse=True)
def inject_fixture(hass_storage):
    """Inject pytest fixtures."""


class TestMQTT:
    """Test the MQTT component."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    @patch("passlib.apps.custom_app_context", Mock(return_value=""))
    @patch("tempfile.NamedTemporaryFile", Mock(return_value=MagicMock()))
    @patch("hbmqtt.broker.Broker", Mock(return_value=MagicMock(start=AsyncMock())))
    @patch("hbmqtt.broker.Broker.start", AsyncMock(return_value=None))
    @patch("homeassistant.components.mqtt.MQTT")
    def test_creating_config_with_pass_and_no_http_pass(self, mock_mqtt):
        """Test if the MQTT server gets started with password.

        Since 0.77, MQTT server has to set up its own password.
        """
        mock_mqtt().async_connect = AsyncMock(return_value=True)
        self.hass.bus.listen_once = MagicMock()
        password = "mqtt_secret"

        assert setup_component(
            self.hass, mqtt.DOMAIN, {mqtt.DOMAIN: {CONF_PASSWORD: password}}
        )
        self.hass.block_till_done()
        assert mock_mqtt.called
        assert mock_mqtt.mock_calls[1][2]["username"] == "homeassistant"
        assert mock_mqtt.mock_calls[1][2]["password"] == password

    @patch("passlib.apps.custom_app_context", Mock(return_value=""))
    @patch("tempfile.NamedTemporaryFile", Mock(return_value=MagicMock()))
    @patch("hbmqtt.broker.Broker", Mock(return_value=MagicMock(start=AsyncMock())))
    @patch("hbmqtt.broker.Broker.start", AsyncMock(return_value=None))
    @patch("homeassistant.components.mqtt.MQTT")
    def test_creating_config_with_pass_and_http_pass(self, mock_mqtt):
        """Test if the MQTT server gets started with password.

        Since 0.77, MQTT server has to set up its own password.
        """
        mock_mqtt().async_connect = AsyncMock(return_value=True)
        self.hass.bus.listen_once = MagicMock()
        password = "mqtt_secret"

        self.hass.config.api = MagicMock(api_password="api_password")
        assert setup_component(
            self.hass, mqtt.DOMAIN, {mqtt.DOMAIN: {CONF_PASSWORD: password}}
        )
        self.hass.block_till_done()
        assert mock_mqtt.called
        assert mock_mqtt.mock_calls[1][2]["username"] == "homeassistant"
        assert mock_mqtt.mock_calls[1][2]["password"] == password

    @patch("tempfile.NamedTemporaryFile", Mock(return_value=MagicMock()))
    @patch("hbmqtt.broker.Broker.start", return_value=mock_coro())
    def test_broker_config_fails(self, mock_run):
        """Test if the MQTT component fails if server fails."""
        from hbmqtt.broker import BrokerException

        mock_run.side_effect = BrokerException

        self.hass.config.api = MagicMock(api_password=None)

        assert not setup_component(
            self.hass, mqtt.DOMAIN, {mqtt.DOMAIN: {mqtt.CONF_EMBEDDED: {}}}
        )
