"""Helpers for Shelly MQTT tests."""
import json


class MockMsg:
    """Mock MQTT Message."""

    def __init__(self, payload, topic):
        """Initialize a mock message."""
        self.topic = topic
        if isinstance(payload, str):
            self.payload = payload
        else:
            self.payload = json.dumps(payload)


def send_msg(callback, payload, topic=""):
    """Send a mock MQTT message to the callback."""
    msg = MockMsg(payload, topic)
    callback(msg)
