"""Test Google Assistant helpers."""
from unittest.mock import Mock
from homeassistant.setup import async_setup_component
from homeassistant.components.google_assistant import helpers
from homeassistant.components.google_assistant.const import EVENT_COMMAND_RECEIVED
from . import MockConfig

from tests.common import async_capture_events, async_mock_service


async def test_google_entity_sync_serialize_with_local_sdk(hass):
    """Test sync serialize attributes of a GoogleEntity."""
    hass.states.async_set("light.ceiling_lights", "off")
    hass.config.api = Mock(port=1234, use_ssl=True)
    config = MockConfig(
        hass=hass,
        local_sdk_webhook_id="mock-webhook-id",
        local_sdk_user_id="mock-user-id",
    )
    entity = helpers.GoogleEntity(hass, config, hass.states.get("light.ceiling_lights"))

    serialized = await entity.sync_serialize()
    assert "otherDeviceIds" not in serialized
    assert "customData" not in serialized

    config.async_enable_local_sdk()

    serialized = await entity.sync_serialize()
    assert serialized["otherDeviceIds"] == [{"deviceId": "light.ceiling_lights"}]
    assert serialized["customData"] == {
        "httpPort": 1234,
        "httpSSL": True,
        "proxyDeviceId": None,
        "webhookId": "mock-webhook-id",
    }


async def test_config_local_sdk(hass, hass_client):
    """Test the local SDK."""
    command_events = async_capture_events(hass, EVENT_COMMAND_RECEIVED)
    turn_on_calls = async_mock_service(hass, "light", "turn_on")
    hass.states.async_set("light.ceiling_lights", "off")

    assert await async_setup_component(hass, "webhook", {})

    config = MockConfig(
        hass=hass,
        local_sdk_webhook_id="mock-webhook-id",
        local_sdk_user_id="mock-user-id",
    )

    client = await hass_client()

    config.async_enable_local_sdk()

    resp = await client.post(
        "/api/webhook/mock-webhook-id",
        json={
            "inputs": [
                {
                    "context": {"locale_country": "US", "locale_language": "en"},
                    "intent": "action.devices.EXECUTE",
                    "payload": {
                        "commands": [
                            {
                                "devices": [{"id": "light.ceiling_lights"}],
                                "execution": [
                                    {
                                        "command": "action.devices.commands.OnOff",
                                        "params": {"on": True},
                                    }
                                ],
                            }
                        ],
                        "structureData": {},
                    },
                }
            ],
            "requestId": "mock-req-id",
        },
    )
    assert resp.status == 200
    result = await resp.json()
    assert result["requestId"] == "mock-req-id"

    assert len(command_events) == 1
    assert command_events[0].context.user_id == config.local_sdk_user_id

    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].context is command_events[0].context

    config.async_disable_local_sdk()

    # Webhook is no longer active
    resp = await client.post("/api/webhook/mock-webhook-id")
    assert resp.status == 200
    assert await resp.read() == b""


async def test_config_local_sdk_if_disabled(hass, hass_client):
    """Test the local SDK."""
    assert await async_setup_component(hass, "webhook", {})

    config = MockConfig(
        hass=hass,
        local_sdk_webhook_id="mock-webhook-id",
        local_sdk_user_id="mock-user-id",
        enabled=False,
    )

    client = await hass_client()

    config.async_enable_local_sdk()

    resp = await client.post(
        "/api/webhook/mock-webhook-id", json={"requestId": "mock-req-id"}
    )
    assert resp.status == 200
    result = await resp.json()
    assert result == {
        "payload": {"errorCode": "deviceTurnedOff"},
        "requestId": "mock-req-id",
    }

    config.async_disable_local_sdk()

    # Webhook is no longer active
    resp = await client.post("/api/webhook/mock-webhook-id")
    assert resp.status == 200
    assert await resp.read() == b""
