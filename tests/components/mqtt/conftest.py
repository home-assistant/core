"""Test fixtures for mqtt component."""
import pytest

from homeassistant import core as ha
from homeassistant.components import mqtt
from homeassistant.setup import async_setup_component

from tests.async_mock import MagicMock, patch
from tests.common import async_fire_mqtt_message


@pytest.fixture
def mqtt_config():
    """Fixture to allow overriding MQTT config."""
    return None


@pytest.fixture
def mqtt_client_mock(hass):
    """Fixture to mock MQTT client."""

    @ha.callback
    def _async_fire_mqtt_message(topic, payload, qos, retain):
        async_fire_mqtt_message(hass, topic, payload, qos, retain)

    with patch("paho.mqtt.client.Client") as mock_client:
        mock_client = mock_client.return_value
        mock_client.connect.return_value = 0
        mock_client.subscribe.return_value = (0, 0)
        mock_client.unsubscribe.return_value = (0, 0)
        mock_client.publish.side_effect = _async_fire_mqtt_message
        yield mock_client


@pytest.fixture
async def mqtt_mock(hass, mqtt_client_mock, mqtt_config):
    """Fixture to mock MQTT component."""
    if mqtt_config is None:
        mqtt_config = {mqtt.CONF_BROKER: "mock-broker"}

    result = await async_setup_component(hass, mqtt.DOMAIN, {mqtt.DOMAIN: mqtt_config})
    assert result
    await hass.async_block_till_done()

    mqtt_component_mock = MagicMock(spec_set=hass.data["mqtt"], wraps=hass.data["mqtt"])
    hass.data["mqtt"].connected = mqtt_component_mock.connected
    mqtt_component_mock._mqttc = mqtt_client_mock

    hass.data["mqtt"] = mqtt_component_mock
    component = hass.data["mqtt"]
    component.reset_mock()
    return component
