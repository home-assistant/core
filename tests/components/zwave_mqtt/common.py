"""Helpers for tests."""
import logging
from pathlib import Path

from asynctest import Mock, patch

from homeassistant import config_entries, core as ha
from homeassistant.components.zwave_mqtt.const import DOMAIN

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def setup_zwave(hass, fixture=None):
    """Set up Z-Wave and load a dump."""
    hass.config.components.add("mqtt")

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave",
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
    )

    entry.add_to_hass(hass)

    with patch("homeassistant.components.mqtt.async_subscribe") as mock_subscribe:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert "zwave_mqtt" in hass.config.components
    assert len(mock_subscribe.mock_calls) == 1
    receive_message = mock_subscribe.mock_calls[0][1][2]

    if fixture is not None:
        data = Path(__file__).parent / "fixtures" / fixture

        with data.open("rt") as fp:
            for line in fp:
                topic, payload = line.strip().split(",", 1)
                receive_message(Mock(topic=topic, payload=payload))

        await hass.async_block_till_done()

    return receive_message


def async_capture_events(hass, event_name):
    """Create a helper that captures events."""
    events = []

    @ha.callback
    def capture_events(event):
        events.append(event)

    hass.bus.async_listen(event_name, capture_events)

    return events
