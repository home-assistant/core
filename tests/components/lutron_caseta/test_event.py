"""Tests for the Lutron Caseta event platform."""

from unittest.mock import patch

from pylutron_caseta import (
    BUTTON_STATUS_MULTITAP,
    BUTTON_STATUS_PRESSED,
    BUTTON_STATUS_RELEASED,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPE, ButtonEventType
from homeassistant.components.lutron_caseta.const import BUTTON_STATUS_LONG_HOLD
from homeassistant.const import EVENT_STATE_CHANGED, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockBridge, async_setup_integration

from tests.common import async_capture_events, snapshot_platform

KEYPAD_BUTTON_ENTITY_ID = (
    "event.hallway_hallway_main_stairs_position_1_keypad_kitchen_pendants"
)
PICO_BUTTON_ENTITY_ID = "event.dining_room_dining_room_pico_stop"
KEYPAD_BUTTON_ID = "1372"
PICO_BUTTON_ID = "111"


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test event entities are created for keypad and pico buttons."""
    with patch("homeassistant.components.lutron_caseta.PLATFORMS", [Platform.EVENT]):
        config_entry = await async_setup_integration(hass, MockBridge)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "button_id", "leap_events", "expected_event_types"),
    [
        pytest.param(
            PICO_BUTTON_ENTITY_ID,
            PICO_BUTTON_ID,
            [BUTTON_STATUS_PRESSED, BUTTON_STATUS_RELEASED],
            [ButtonEventType.PRESS_START, ButtonEventType.PRESS_END],
            id="pico_press_and_release",
        ),
        # An orphan release is the status replayed by the bridge on reconnect
        pytest.param(
            PICO_BUTTON_ENTITY_ID,
            PICO_BUTTON_ID,
            [BUTTON_STATUS_RELEASED],
            [],
            id="pico_orphan_release",
        ),
        pytest.param(
            PICO_BUTTON_ENTITY_ID,
            PICO_BUTTON_ID,
            [BUTTON_STATUS_PRESSED, BUTTON_STATUS_MULTITAP, BUTTON_STATUS_RELEASED],
            [ButtonEventType.PRESS_START, ButtonEventType.PRESS_END],
            id="pico_multi_tap_ignored",
        ),
        # Keypads may never report a release, so repeated presses must each fire
        pytest.param(
            KEYPAD_BUTTON_ENTITY_ID,
            KEYPAD_BUTTON_ID,
            [BUTTON_STATUS_PRESSED, BUTTON_STATUS_PRESSED],
            [ButtonEventType.PRESS_END, ButtonEventType.PRESS_END],
            id="keypad_press_only",
        ),
        pytest.param(
            KEYPAD_BUTTON_ENTITY_ID,
            KEYPAD_BUTTON_ID,
            [BUTTON_STATUS_PRESSED, BUTTON_STATUS_RELEASED],
            [ButtonEventType.PRESS_END],
            id="keypad_release_ignored",
        ),
        pytest.param(
            KEYPAD_BUTTON_ENTITY_ID,
            KEYPAD_BUTTON_ID,
            [BUTTON_STATUS_MULTITAP, BUTTON_STATUS_LONG_HOLD],
            [],
            id="keypad_multi_tap_and_long_hold_ignored",
        ),
    ],
)
async def test_button_event_mapping(
    hass: HomeAssistant,
    entity_id: str,
    button_id: str,
    leap_events: list[str],
    expected_event_types: list[ButtonEventType],
) -> None:
    """Test LEAP button events are mapped to standard button event types."""
    config_entry = await async_setup_integration(hass, MockBridge)
    bridge = config_entry.runtime_data.bridge
    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)

    for leap_event in leap_events:
        bridge.call_button_subscribers(button_id, leap_event)
    await hass.async_block_till_done()

    assert [
        event.data["new_state"].attributes[ATTR_EVENT_TYPE]
        for event in state_changes
        if event.data["entity_id"] == entity_id
    ] == expected_event_types
