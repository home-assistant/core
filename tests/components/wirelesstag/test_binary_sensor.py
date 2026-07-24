"""Tests for the Wireless Sensor Tags binary sensor platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.wirelesstag.const import SIGNAL_BINARY_EVENT_UPDATE
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

CONFIG = {
    "wirelesstag": {"username": "foo@bar.com", "password": "secret"},
    "binary_sensor": {
        "platform": "wirelesstag",
        "monitored_conditions": ["motion", "dry", "wet"],
    },
}

UUID = "00000000-0000-0000-0000-000000000001"
TAG_ID = 1
MAC = "ABCDEF012345"

EVENT_NAMES = {"motion": "Motion", "dry": "Too dry", "wet": "Too wet"}


def _mock_tag() -> MagicMock:
    """Return a mocked wirelesstagpy SensorTag with motion/dry/wet events off."""
    tag = MagicMock()
    tag.uuid = UUID
    tag.tag_id = TAG_ID
    tag.tag_manager_mac = MAC
    tag.name = "Bedroom"
    tag.is_alive = True
    tag.supported_binary_events_types = list(EVENT_NAMES)
    tag.battery_remaining = 0.85
    tag.battery_volts = 3.0
    tag.signal_strength = -60
    tag.is_in_range = True
    tag.power_consumption = 1.5

    events = {}
    for event_type, human_readable_name in EVENT_NAMES.items():
        event = MagicMock()
        event.human_readable_name = human_readable_name
        event.is_state_on = False
        events[event_type] = event
    tag.event.__getitem__.side_effect = events.__getitem__
    return tag


@pytest.mark.parametrize("event_type", ["motion", "dry", "wet"])
async def test_binary_sensor_receives_push_update(
    hass: HomeAssistant,
    event_type: str,
) -> None:
    """Test binary sensors update from push events for every event type.

    The push side dispatches the signal keyed by the library event type, so the
    entity must subscribe with the same key. Events whose device_class is None
    (dry/wet) previously subscribed with "None" and never updated.
    """
    tag = _mock_tag()
    with patch("homeassistant.components.wirelesstag.WirelessTags") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.load_tags.return_value = {tag.uuid: tag}

        assert await async_setup_component(hass, "wirelesstag", CONFIG)
        await hass.async_block_till_done()
        assert await async_setup_component(hass, "binary_sensor", CONFIG)
        await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "binary_sensor", "wirelesstag", f"{UUID}_{event_type}"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_OFF

    # Simulate a push notification turning the event on.
    tag.event[event_type].is_state_on = True
    async_dispatcher_send(
        hass, SIGNAL_BINARY_EVENT_UPDATE.format(TAG_ID, event_type, MAC), tag
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON
