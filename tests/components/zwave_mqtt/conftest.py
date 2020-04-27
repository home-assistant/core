"""Helpers for tests."""
import json

from asynctest import patch
import pytest


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
