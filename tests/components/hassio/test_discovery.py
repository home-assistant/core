"""Test config flow."""
from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.components.mqtt import DOMAIN as MQTT_DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STARTED
from homeassistant.setup import async_setup_component

from tests.common import MockModule, mock_entity_platform, mock_integration


@pytest.fixture
async def mock_mqtt(hass):
    """Mock the MQTT integration's config flow."""
    mock_integration(hass, MockModule(MQTT_DOMAIN))
    mock_entity_platform(hass, f"config_flow.{MQTT_DOMAIN}", None)

    with patch.dict(config_entries.HANDLERS):

        class MqttFlow(config_entries.ConfigFlow, domain=MQTT_DOMAIN):
            """Test flow."""

            VERSION = 1

            async_step_hassio = AsyncMock(return_value={"type": "abort"})

        yield MqttFlow


async def test_hassio_discovery_startup(hass, aioclient_mock, hassio_client, mock_mqtt):
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

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2
    assert mock_mqtt.async_step_hassio.called
    mock_mqtt.async_step_hassio.assert_called_with(
        HassioServiceInfo(
            config={
                "broker": "mock-broker",
                "port": 1883,
                "username": "mock-user",
                "password": "mock-pass",
                "protocol": "3.1.1",
                "addon": "Mosquitto Test",
            }
        )
    )


async def test_hassio_discovery_startup_done(
    hass, aioclient_mock, hassio_client, mock_mqtt
):
    """Test startup and discovery with hass discovery."""
    aioclient_mock.post(
        "http://127.0.0.1/supervisor/options",
        json={"result": "ok", "data": {}},
    )
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
    ):
        await hass.async_start()
        await async_setup_component(hass, "hassio", {})
        await hass.async_block_till_done()

        assert aioclient_mock.call_count == 2
        assert mock_mqtt.async_step_hassio.called
        mock_mqtt.async_step_hassio.assert_called_with(
            HassioServiceInfo(
                config={
                    "broker": "mock-broker",
                    "port": 1883,
                    "username": "mock-user",
                    "password": "mock-pass",
                    "protocol": "3.1.1",
                    "addon": "Mosquitto Test",
                }
            )
        )


async def test_hassio_discovery_webhook(hass, aioclient_mock, hassio_client, mock_mqtt):
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

    resp = await hassio_client.post(
        "/api/hassio_push/discovery/testuuid",
        json={"addon": "mosquitto", "service": "mqtt", "uuid": "testuuid"},
    )
    await hass.async_block_till_done()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert resp.status == HTTPStatus.OK
    assert aioclient_mock.call_count == 2
    assert mock_mqtt.async_step_hassio.called
    mock_mqtt.async_step_hassio.assert_called_with(
        HassioServiceInfo(
            config={
                "broker": "mock-broker",
                "port": 1883,
                "username": "mock-user",
                "password": "mock-pass",
                "protocol": "3.1.1",
                "addon": "Mosquitto Test",
            }
        )
    )
