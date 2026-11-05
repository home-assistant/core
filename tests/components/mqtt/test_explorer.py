"""Tests for the MQTT topic explorer websocket API."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_mqtt_message, async_fire_time_changed
from pytest_homeassistant.typing import MqttMockHAClientGenerator, WebSocketGenerator

from homeassistant.components import mqtt
from homeassistant.components.mqtt.explorer import MAX_PAYLOAD_SIZE
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util


async def test_explorer(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the explorer reports topics, rates and the newest payloads."""
    await mqtt_mock_entry()
    await mqtt.async_subscribe(hass, "sensor/kitchen", callback(lambda msg: None))
    client = await hass_ws_client(hass)
    started = dt_util.utcnow().timestamp()

    await client.send_json(
        {"id": 5, "type": "mqtt/explorer/subscribe", "topic": "sensor/#"}
    )
    assert (await client.receive_json())["success"]
    assert (await client.receive_json())["event"] == {
        "interval": 2.0,
        "now": started,
        "started": started,
        "total": {
            "topics": 0,
            "messages": 0,
            "bytes": 0,
            "message_rate": 0.0,
            "byte_rate": 0.0,
            "dropped_messages": 0,
        },
        "topics": [],
        "messages": [],
    }

    for value in range(7):
        async_fire_mqtt_message(hass, "sensor/kitchen", f'{{"temp": {value}}}')
    async_fire_mqtt_message(hass, "sensor/garage", b"\xff\xfe", qos=1, retain=True)
    async_fire_mqtt_message(hass, "other/topic", "not below the filter")
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)

    event = (await client.receive_json())["event"]
    now = started + 2
    assert event["total"] == {
        "topics": 2,
        "messages": 8,
        "bytes": 79,
        "message_rate": 4.0,
        "byte_rate": 39.5,
        "dropped_messages": 0,
    }
    assert event["topics"] == [
        {
            "topic": "sensor/kitchen",
            "messages": 7,
            "bytes": 77,
            "message_rate": 3.5,
            "byte_rate": 38.5,
            "last_received": started,
            "retained": False,
            "qos": 0,
            "subscriptions": 1,
        },
        {
            "topic": "sensor/garage",
            "messages": 1,
            "bytes": 2,
            "message_rate": 0.5,
            "byte_rate": 1.0,
            "last_received": started,
            "retained": True,
            "qos": 1,
            "subscriptions": 0,
        },
    ]
    assert [message["payload"] for message in event["messages"]] == [
        '{"temp": 2}',
        '{"temp": 3}',
        '{"temp": 4}',
        '{"temp": 5}',
        '{"temp": 6}',
        "b'\\xff\\xfe'",
    ]
    assert event["now"] == now

    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)
    event = (await client.receive_json())["event"]
    assert event["topics"] == []
    assert event["messages"] == []
    assert event["total"]["message_rate"] == 0.0
    assert event["total"]["messages"] == 8

    await client.send_json({"id": 6, "type": "unsubscribe_events", "subscription": 5})
    assert (await client.receive_json())["success"]


async def test_explorer_truncates_large_payload(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a large payload is cut off and marked as truncated."""
    await mqtt_mock_entry()
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "mqtt/explorer/subscribe"})
    assert (await client.receive_json())["success"]
    await client.receive_json()

    async_fire_mqtt_message(hass, "big", "x" * (MAX_PAYLOAD_SIZE + 10))
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)

    message = (await client.receive_json())["event"]["messages"][0]
    assert message["payload"] == "x" * MAX_PAYLOAD_SIZE
    assert message["truncated"] is True
    assert message["size"] == MAX_PAYLOAD_SIZE + 10


async def test_explorer_not_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Test the explorer requires an admin."""
    await mqtt_mock_entry()
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    await client.send_json({"id": 5, "type": "mqtt/explorer/subscribe"})
    response = await client.receive_json()
    assert response["error"]["code"] == "unauthorized"


async def test_explorer_not_loaded(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the explorer reports MQTT isn't loaded without a config entry."""
    assert await async_setup_component(hass, mqtt.DOMAIN, {})
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "mqtt/explorer/subscribe"})
    response = await client.receive_json()
    assert response["error"]["code"] == "not_loaded"


async def test_explorer_topic_limit(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test messages on new topics beyond the limit are only counted as dropped."""
    await mqtt_mock_entry()
    client = await hass_ws_client(hass)
    with patch("homeassistant.components.mqtt.explorer.MAX_TOPICS", 2):
        await client.send_json({"id": 5, "type": "mqtt/explorer/subscribe"})
        assert (await client.receive_json())["success"]
        await client.receive_json()

        for topic in ("a", "b", "c", "c", "a"):
            async_fire_mqtt_message(hass, topic, "1")
        await hass.async_block_till_done()
        freezer.tick(timedelta(seconds=2))
        async_fire_time_changed(hass)

        event = (await client.receive_json())["event"]
    assert [topic["topic"] for topic in event["topics"]] == ["a", "b"]
    assert event["total"]["topics"] == 2
    assert event["total"]["messages"] == 3
    assert event["total"]["dropped_messages"] == 2
