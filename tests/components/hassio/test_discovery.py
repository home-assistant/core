"""Test config flow."""
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.setup import async_setup_component

from tests.async_mock import Mock, patch


async def test_hassio_discovery_startup(hass, aioclient_mock, hassio_client):
    """Test startup and discovery after event."""
    aioclient_mock.get(
        "http://127.0.0.1/discovery",
        json={
            "result": "ok",
            "data": {
                "discovery": [
                    {
                        "service": "mqtt",
                        "uuid": "test",
                        "addon": "mosquitto",
                        "config": {
                            "broker": "mock-broker",
                            "port": 1883,
                            "username": "mock-user",
                            "password": "mock-pass",
                            "protocol": "3.1.1",
                        },
                    }
                ]
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/addons/mosquitto/info",
        json={"result": "ok", "data": {"name": "Mosquitto Test"}},
    )

    assert aioclient_mock.call_count == 0

    with patch(
        "homeassistant.components.mqtt.config_flow.FlowHandler.async_step_hassio",
        return_value={"type": "abort"},
    ) as mock_mqtt:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        assert aioclient_mock.call_count == 2
        assert mock_mqtt.called
        mock_mqtt.assert_called_with(
            {
                "broker": "mock-broker",
                "port": 1883,
                "username": "mock-user",
                "password": "mock-pass",
                "protocol": "3.1.1",
                "addon": "Mosquitto Test",
            }
        )


async def test_hassio_discovery_startup_done(hass, aioclient_mock, hassio_client):
    """Test startup and discovery with hass discovery."""
    aioclient_mock.get(
        "http://127.0.0.1/discovery",
        json={
            "result": "ok",
            "data": {
                "discovery": [
                    {
                        "service": "mqtt",
                        "uuid": "test",
                        "addon": "mosquitto",
                        "config": {
                            "broker": "mock-broker",
                            "port": 1883,
                            "username": "mock-user",
                            "password": "mock-pass",
                            "protocol": "3.1.1",
                        },
                    }
                ]
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/addons/mosquitto/info",
        json={"result": "ok", "data": {"name": "Mosquitto Test"}},
    )

    with patch(
        "homeassistant.components.hassio.HassIO.update_hass_api",
        return_value={"result": "ok"},
    ), patch(
        "homeassistant.components.hassio.HassIO.get_info",
        Mock(side_effect=HassioAPIError()),
    ), patch(
        "homeassistant.components.mqtt.config_flow.FlowHandler.async_step_hassio",
        return_value={"type": "abort"},
    ) as mock_mqtt:
        await hass.async_start()
        await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()

        assert aioclient_mock.call_count == 2
        assert mock_mqtt.called
        mock_mqtt.assert_called_with(
            {
                "broker": "mock-broker",
                "port": 1883,
                "username": "mock-user",
                "password": "mock-pass",
                "protocol": "3.1.1",
                "addon": "Mosquitto Test",
            }
        )


async def test_hassio_discovery_webhook(hass, aioclient_mock, hassio_client):
    """Test discovery webhook."""
    aioclient_mock.get(
        "http://127.0.0.1/discovery/testuuid",
        json={
            "result": "ok",
            "data": {
                "service": "mqtt",
                "uuid": "test",
                "addon": "mosquitto",
                "config": {
                    "broker": "mock-broker",
                    "port": 1883,
                    "username": "mock-user",
                    "password": "mock-pass",
                    "protocol": "3.1.1",
                },
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/addons/mosquitto/info",
        json={"result": "ok", "data": {"name": "Mosquitto Test"}},
    )

    with patch(
        "homeassistant.components.mqtt.config_flow.FlowHandler.async_step_hassio",
        return_value={"type": "abort"},
    ) as mock_mqtt:
        resp = await hassio_client.post(
            "/api/hassio_push/discovery/testuuid",
            json={"addon": "mosquitto", "service": "mqtt", "uuid": "testuuid"},
        )
        await hass.async_block_till_done()

        assert resp.status == 200
        assert aioclient_mock.call_count == 2
        assert mock_mqtt.called
        mock_mqtt.assert_called_with(
            {
                "broker": "mock-broker",
                "port": 1883,
                "username": "mock-user",
                "password": "mock-pass",
                "protocol": "3.1.1",
                "addon": "Mosquitto Test",
            }
        )
