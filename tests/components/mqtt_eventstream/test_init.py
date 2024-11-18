"""The tests for the MQTT eventstream component."""

import json
from unittest.mock import ANY, patch

import pytest

import homeassistant.components.mqtt_eventstream as eventstream
from homeassistant.const import EVENT_STATE_CHANGED, MATCH_ALL
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.json import JSONEncoder
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    async_fire_mqtt_message,
    async_fire_time_changed,
    mock_state_change_event,
)
from tests.typing import MqttMockHAClient


async def add_eventstream(
    hass: HomeAssistant,
    sub_topic: str | None = None,
    pub_topic: str | None = None,
    ignore_event: list[str] | None = None,
) -> bool:
    """Add a mqtt_eventstream component."""
    config = {}
    if sub_topic:
        config["subscribe_topic"] = sub_topic
    if pub_topic:
        config["publish_topic"] = pub_topic
    if ignore_event:
        config["ignore_event"] = ignore_event
    return await async_setup_component(
        hass, eventstream.DOMAIN, {eventstream.DOMAIN: config}
    )


async def test_setup_succeeds(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test the success of the setup."""
    assert await add_eventstream(hass)


async def test_setup_no_mqtt(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the failure of the setup if mqtt is not set up."""
    assert not await add_eventstream(hass)
    assert "MQTT integration is not available" in caplog.text


async def test_setup_with_pub(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test the setup with subscription."""
    # Should start off with no listeners for all events
    assert not hass.bus.async_listeners().get("*")

    assert await add_eventstream(hass, pub_topic="bar")
    await hass.async_block_till_done()

    # Verify that the event handler has been added as a listener
    assert hass.bus.async_listeners().get("*") == 1


async def test_subscribe(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test the subscription."""
    sub_topic = "foo"
    assert await add_eventstream(hass, sub_topic=sub_topic)
    await hass.async_block_till_done()

    # Verify that the this entity was subscribed to the topic
    mqtt_mock.async_subscribe.assert_called_with(sub_topic, ANY, 0, ANY, ANY)


async def test_state_changed_event_sends_message(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the sending of a new message if event changed."""
    now = dt_util.as_utc(dt_util.now())
    e_id = "fake.entity"
    pub_topic = "bar"
    with patch(
        ("homeassistant.core.dt_util.utcnow"),
        return_value=now,
    ):
        # Add the eventstream component for publishing events
        assert await add_eventstream(hass, pub_topic=pub_topic)
        await hass.async_block_till_done()

        # Reset the mock because it will have already gotten calls for the
        # mqtt_eventstream state change on initialization, etc.
        mqtt_mock.async_publish.reset_mock()

        # Set a state of an entity
        mock_state_change_event(hass, State(e_id, "on"))
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    # The order of the JSON is indeterminate,
    # so first just check that publish was called
    mqtt_mock.async_publish.assert_called_with(pub_topic, ANY, 0, False)
    assert mqtt_mock.async_publish.called

    # Get the actual call to publish and make sure it was the one
    # we were looking for
    msg = mqtt_mock.async_publish.call_args[0][1]
    event = {}
    event["event_type"] = EVENT_STATE_CHANGED
    new_state = {
        "attributes": {},
        "entity_id": e_id,
        "last_changed": now.isoformat(),
        "last_reported": now.isoformat(),
        "last_updated": now.isoformat(),
        "state": "on",
    }
    event["event_data"] = {"new_state": new_state, "entity_id": e_id, "old_state": None}

    # Verify that the message received was that expected
    result = json.loads(msg)
    result["event_data"]["new_state"].pop("context")
    assert result == event


async def test_time_event_does_not_send_message(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the sending of a new message if time event."""
    assert await add_eventstream(hass, pub_topic="bar")
    await hass.async_block_till_done()

    # Reset the mock because it will have already gotten calls for the
    # mqtt_eventstream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert not mqtt_mock.async_publish.called


async def test_receiving_remote_event_fires_hass_event(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the receiving of the remotely fired event."""
    sub_topic = "foo"
    assert await add_eventstream(hass, sub_topic=sub_topic)
    await hass.async_block_till_done()

    calls = []

    @callback
    def listener(_):
        calls.append(1)

    hass.bus.async_listen_once("test_event", listener)
    await hass.async_block_till_done()

    payload = json.dumps(
        {"event_type": "test_event", "event_data": {}}, cls=JSONEncoder
    )
    async_fire_mqtt_message(hass, sub_topic, payload)
    await hass.async_block_till_done()

    assert len(calls) == 1

    await hass.async_block_till_done()


async def test_receiving_blocked_event_fires_hass_event(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the receiving of blocked event does not fire."""
    sub_topic = "foo"
    assert await add_eventstream(hass, sub_topic=sub_topic)
    await hass.async_block_till_done()

    calls = []

    @callback
    def listener(_):
        calls.append(1)

    hass.bus.async_listen(MATCH_ALL, listener)
    await hass.async_block_till_done()

    for event in eventstream.BLOCKED_EVENTS:
        payload = json.dumps({"event_type": event, "event_data": {}}, cls=JSONEncoder)
        async_fire_mqtt_message(hass, sub_topic, payload)
        await hass.async_block_till_done()

    assert len(calls) == 0

    await hass.async_block_till_done()


async def test_ignored_event_doesnt_send_over_stream(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the ignoring of sending events if defined."""
    assert await add_eventstream(hass, pub_topic="bar", ignore_event=["state_changed"])
    await hass.async_block_till_done()

    e_id = "entity.test_id"
    event = {}
    event["event_type"] = EVENT_STATE_CHANGED
    new_state = {"state": "on", "entity_id": e_id, "attributes": {}}
    event["event_data"] = {"new_state": new_state, "entity_id": e_id}

    # Reset the mock because it will have already gotten calls for the
    # mqtt_eventstream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    # Set a state of an entity
    mock_state_change_event(hass, State(e_id, "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert not mqtt_mock.async_publish.called


async def test_wrong_ignored_event_sends_over_stream(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the ignoring of sending events if defined."""
    assert await add_eventstream(hass, pub_topic="bar", ignore_event=["statee_changed"])
    await hass.async_block_till_done()

    e_id = "entity.test_id"
    event = {}
    event["event_type"] = EVENT_STATE_CHANGED
    new_state = {"state": "on", "entity_id": e_id, "attributes": {}}
    event["event_data"] = {"new_state": new_state, "entity_id": e_id}

    # Reset the mock because it will have already gotten calls for the
    # mqtt_eventstream state change on initialization, etc.
    mqtt_mock.async_publish.reset_mock()

    # Set a state of an entity
    mock_state_change_event(hass, State(e_id, "on"))
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert mqtt_mock.async_publish.called
