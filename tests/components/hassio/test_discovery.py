"""Test config flow."""
from unittest.mock import patch, Mock

from homeassistant.setup import async_setup_component
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.const import EVENT_HOMEASSISTANT_START, HTTP_HEADER_HA_AUTH

from tests.common import mock_coro
from . import API_PASSWORD


async def test_hassio_discovery_startup(hass, aioclient_mock, hassio_client):
    """Test startup and discovery after event."""
    aioclient_mock.get(
        "http://127.0.0.1/discovery", json={
            'result': 'ok', 'data': {'discovery': [
                {
                    "service": "mqtt", "uuid": "test",
                    "addon": "mosquitto", "config":
                    {
                        'broker': 'mock-broker',
                        'port': 1883,
                        'username': 'mock-user',
                        'password': 'mock-pass',
                        'protocol': '3.1.1'
                    }
                }
            ]}})
    aioclient_mock.get(
        "http://127.0.0.1/addons/mosquitto/info", json={
            'result': 'ok', 'data': {'name': "Mosquitto Test"}
        })

    assert aioclient_mock.call_count == 0

    with patch('homeassistant.components.mqtt.'
               'config_flow.FlowHandler.async_step_hassio',
               Mock(return_value=mock_coro({"type": "abort"}))) as mock_mqtt:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        assert aioclient_mock.call_count == 2
        assert mock_mqtt.called
        mock_mqtt.assert_called_with({
            'broker': 'mock-broker', 'port': 1883, 'username': 'mock-user',
            'password': 'mock-pass', 'protocol': '3.1.1',
            'addon': 'Mosquitto Test',
        })


async def test_hassio_discovery_startup_done(hass, aioclient_mock,
                                             hassio_client):
    """Test startup and discovery with hass discovery."""
    aioclient_mock.get(
        "http://127.0.0.1/discovery", json={
            'result': 'ok', 'data': {'discovery': [
                {
                    "service": "mqtt", "uuid": "test",
                    "addon": "mosquitto", "config":
                    {
                        'broker': 'mock-broker',
                        'port': 1883,
                        'username': 'mock-user',
                        'password': 'mock-pass',
                        'protocol': '3.1.1'
                    }
                }
            ]}})
    aioclient_mock.get(
        "http://127.0.0.1/addons/mosquitto/info", json={
            'result': 'ok', 'data': {'name': "Mosquitto Test"}
        })

    with patch('homeassistant.components.hassio.HassIO.update_hass_api',
               Mock(return_value=mock_coro({"result": "ok"}))), \
            patch('homeassistant.components.hassio.HassIO.'
                  'get_homeassistant_info',
                  Mock(side_effect=HassioAPIError())), \
            patch('homeassistant.components.mqtt.'
                  'config_flow.FlowHandler.async_step_hassio',
                  Mock(return_value=mock_coro({"type": "abort"}))
                  ) as mock_mqtt:
        await hass.async_start()
        await async_setup_component(hass, 'hassio', {
            'http': {
                'api_password': API_PASSWORD
            }
        })
        await hass.async_block_till_done()

        assert aioclient_mock.call_count == 2
        assert mock_mqtt.called
        mock_mqtt.assert_called_with({
            'broker': 'mock-broker', 'port': 1883, 'username': 'mock-user',
            'password': 'mock-pass', 'protocol': '3.1.1',
            'addon': 'Mosquitto Test',
        })


async def test_hassio_discovery_webhook(hass, aioclient_mock, hassio_client):
    """Test discovery webhook."""
    aioclient_mock.get(
        "http://127.0.0.1/discovery/testuuid", json={
            'result': 'ok', 'data':
                {
                    "service": "mqtt", "uuid": "test",
                    "addon": "mosquitto", "config":
                    {
                        'broker': 'mock-broker',
                        'port': 1883,
                        'username': 'mock-user',
                        'password': 'mock-pass',
                        'protocol': '3.1.1'
                    }
                }
            })
    aioclient_mock.get(
        "http://127.0.0.1/addons/mosquitto/info", json={
            'result': 'ok', 'data': {'name': "Mosquitto Test"}
        })

    with patch('homeassistant.components.mqtt.'
               'config_flow.FlowHandler.async_step_hassio',
               Mock(return_value=mock_coro({"type": "abort"}))) as mock_mqtt:
        resp = await hassio_client.post(
            '/api/hassio_push/discovery/testuuid', headers={
                HTTP_HEADER_HA_AUTH: API_PASSWORD
            }, json={
                "addon": "mosquitto", "service": "mqtt", "uuid": "testuuid"
            }
        )
        await hass.async_block_till_done()

        assert resp.status == 200
        assert aioclient_mock.call_count == 2
        assert mock_mqtt.called
        mock_mqtt.assert_called_with({
            'broker': 'mock-broker', 'port': 1883, 'username': 'mock-user',
            'password': 'mock-pass', 'protocol': '3.1.1',
            'addon': 'Mosquitto Test',
        })
