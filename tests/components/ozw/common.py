"""Helpers for tests."""
import json

from homeassistant import config_entries
from homeassistant.components.zwave_mqtt.const import DOMAIN

from tests.async_mock import Mock, patch
from tests.common import MockConfigEntry


async def setup_zwave(hass, entry=None, fixture=None):
    """Set up Z-Wave and load a dump."""
    hass.config.components.add("mqtt")

    if entry is None:
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Z-Wave",
            connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        )

        entry.add_to_hass(hass)

    with patch("homeassistant.components.mqtt.async_subscribe") as mock_subscribe:
        mock_subscribe.return_value = Mock()
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert "zwave_mqtt" in hass.config.components
    assert len(mock_subscribe.mock_calls) == 1
    receive_message = mock_subscribe.mock_calls[0][1][2]

    if fixture is not None:
        for line in fixture.split("\n"):
            topic, payload = line.strip().split(",", 1)
            receive_message(Mock(topic=topic, payload=payload))

        await hass.async_block_till_done()

    return receive_message


class MQTTMessage:
    """Represent a mock MQTT message."""

    def __init__(self, topic, payload):
        """Set up message."""
        self.topic = topic
        self.payload = payload

    def decode(self):
        """Decode message payload from a string to a json dict."""
        self.payload = json.loads(self.payload)

    def encode(self):
        """Encode message payload into a string."""
        self.payload = json.dumps(self.payload)
