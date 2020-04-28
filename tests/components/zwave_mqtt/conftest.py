"""Helpers for tests."""
import json

from asynctest import patch
import pytest

from .common import MQTTMessage

from tests.common import load_fixture


@pytest.fixture(name="sent_messages")
def sent_messages_fixture():
    """Fixture to capture sent messages."""
    sent_messages = []

    with patch(
        "homeassistant.components.mqtt.async_publish",
        side_effect=lambda hass, topic, payload: sent_messages.append(
            {"topic": topic, "payload": json.loads(payload)}
        ),
    ):
        yield sent_messages


@pytest.fixture(name="switch_msg")
async def switch_msg_fixture(hass):
    """Return a mock MQTT msg with a switch actuator message."""
    switch_json = json.loads(
        await hass.async_add_executor_job(load_fixture, "zwave_mqtt/switch.json")
    )
    message = MQTTMessage(topic=switch_json["topic"], payload=switch_json["payload"])
    message.encode()
    return message
