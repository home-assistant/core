"""Tests for the MQTT topic explorer websocket API."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
)
from pytest_homeassistant.typing import MqttMockHAClientGenerator, WebSocketGenerator

from homeassistant.components import mqtt
from homeassistant.components.mqtt.explorer import MAX_PAYLOAD_SIZE
from homeassistant.components.mqtt.models import DATA_MQTT, ReceiveMessage
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


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        pytest.param("x" * (MAX_PAYLOAD_SIZE + 10), "x" * MAX_PAYLOAD_SIZE, id="ascii"),
        pytest.param(
            "x" * (MAX_PAYLOAD_SIZE - 1) + "é",
            "x" * (MAX_PAYLOAD_SIZE - 1),
            id="split_code_point",
        ),
    ],
)
async def test_explorer_truncates_large_payload(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    freezer: FrozenDateTimeFactory,
    payload: str,
    expected: str,
) -> None:
    """Test a large payload is cut off and marked as truncated."""
    await mqtt_mock_entry()
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "mqtt/explorer/subscribe"})
    assert (await client.receive_json())["success"]
    await client.receive_json()

    async_fire_mqtt_message(hass, "big", payload.encode())
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)

    message = (await client.receive_json())["event"]["messages"][0]
    assert message["payload"] == expected
    assert message["truncated"] is True
    assert message["size"] == len(payload.encode())


async def test_explorer_shares_topic_with_text_subscriber(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the explorer and a text subscriber on the same filter get their own payload."""
    await mqtt_mock_entry()
    received: list[ReceiveMessage] = []

    @callback
    def record(msg: ReceiveMessage) -> None:
        received.append(msg)

    await mqtt.async_subscribe(hass, "sensor/kitchen", record)
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "mqtt/explorer/subscribe", "topic": "sensor/kitchen"}
    )
    assert (await client.receive_json())["success"]
    await client.receive_json()

    async_fire_mqtt_message(hass, "sensor/kitchen", "é".encode())
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass)

    assert received[0].payload == "é"
    message = (await client.receive_json())["event"]["messages"][0]
    assert message["payload"] == "é"
    assert message["size"] == 2


@pytest.mark.parametrize("interval", [0.5, 61, 1e20])
async def test_explorer_invalid_interval(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    interval: float,
) -> None:
    """Test an interval out of range is rejected before subscribing."""
    await mqtt_mock_entry()
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 5, "type": "mqtt/explorer/subscribe", "interval": interval}
    )
    response = await client.receive_json()
    assert response["error"]["code"] == "invalid_format"
    assert hass.data[DATA_MQTT].client.async_count_matching_subscriptions("a") == 0


@pytest.mark.usefixtures("mqtt_client_mock")
async def test_explorer_stops_on_reload(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the explorer subscription is not restored after an MQTT reload."""
    entry = MockConfigEntry(
        domain=mqtt.DOMAIN,
        data={mqtt.CONF_BROKER: "test-broker"},
        version=mqtt.CONFIG_ENTRY_VERSION,
        minor_version=mqtt.CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, mqtt.DOMAIN, {})
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "mqtt/explorer/subscribe"})
    assert (await client.receive_json())["success"]
    await client.receive_json()
    assert hass.data[DATA_MQTT].client.async_count_matching_subscriptions("a") == 1

    with patch("homeassistant.config.load_yaml_config_file", return_value={}):
        assert await hass.config_entries.async_reload(entry.entry_id)
    assert hass.data[DATA_MQTT].client.async_count_matching_subscriptions("a") == 0

    await client.send_json({"id": 6, "type": "unsubscribe_events", "subscription": 5})
    assert (await client.receive_json())["success"]


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
