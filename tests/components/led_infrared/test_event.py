"""Tests for the LED Infrared event platform."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import patch

from infrared_protocols.codes.generic.led import (
    Generic13KeyCode,
    Generic24KeyCode,
    Generic40KeyCode,
    Generic44KeyCode,
)
from infrared_protocols.commands.nec import NECCommand
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import EventEntityStateAttribute
from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.components.led_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
    LEDIrDeviceType,
)
from homeassistant.components.light import LightEntityStateAttribute
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import EVENT_ENTITY_ID, LIGHT_ENTITY_ID, LEDIrKeyCode

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.infrared import EMITTER_ENTITY_ID, RECEIVER_ENTITY_ID
from tests.components.infrared.common import MockInfraredReceiverEntity


@pytest.fixture
def event_only() -> Generator[None]:
    """Enable only the event platform."""
    with patch(
        "homeassistant.components.led_infrared.PLATFORMS",
        [Platform.EVENT],
    ):
        yield


@pytest.mark.parametrize(
    "config_entry",
    [
        LEDIrDeviceType.GENERIC_13_KEY,
        LEDIrDeviceType.GENERIC_24_KEY,
        LEDIrDeviceType.GENERIC_40_KEY,
        LEDIrDeviceType.GENERIC_44_KEY,
    ],
    indirect=True,
)
@pytest.mark.usefixtures("event_only", "mock_infrared_receiver_entity")
async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test states of event platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


# Every code the remote can send, with the light state and effect it leaves
# behind. One entry replays a whole remote, so the codes are grouped in an order
# that keeps each expectation independent of the presses before it: codes the
# light ignores run first, while it is still unknown, then on and off, which must
# not have an effect set yet, then the effect and colour codes, each of which
# overwrites the previous effect.
_RECEIVED_COMMANDS: dict[
    LEDIrDeviceType, list[tuple[LEDIrKeyCode, str, str | None]]
] = {
    LEDIrDeviceType.GENERIC_13_KEY: [
        (Generic13KeyCode.TIMER, STATE_UNKNOWN, None),
        (Generic13KeyCode.BRIGHTNESS_UP, STATE_UNKNOWN, None),
        (Generic13KeyCode.BRIGHTNESS_DOWN, STATE_UNKNOWN, None),
        (Generic13KeyCode.ON, "on", None),
        (Generic13KeyCode.OFF, "off", None),
        (Generic13KeyCode.MODE_1, "on", "mode_1"),
        (Generic13KeyCode.MODE_2, "on", "mode_2"),
        (Generic13KeyCode.MODE_3, "on", "mode_3"),
        (Generic13KeyCode.MODE_4, "on", "mode_4"),
        (Generic13KeyCode.MODE_5, "on", "mode_5"),
        (Generic13KeyCode.MODE_6, "on", "mode_6"),
        (Generic13KeyCode.MODE_7, "on", "mode_7"),
        (Generic13KeyCode.MODE_8, "on", "mode_8"),
    ],
    LEDIrDeviceType.GENERIC_24_KEY: [
        (Generic24KeyCode.BRIGHTNESS_UP, STATE_UNKNOWN, None),
        (Generic24KeyCode.BRIGHTNESS_DOWN, STATE_UNKNOWN, None),
        (Generic24KeyCode.ON, "on", None),
        (Generic24KeyCode.OFF, "off", None),
        (Generic24KeyCode.FLASH, "on", "flash"),
        (Generic24KeyCode.STROBE, "on", "strobe"),
        (Generic24KeyCode.FADE, "on", "fade"),
        (Generic24KeyCode.SMOOTH, "on", "smooth"),
        (Generic24KeyCode.RED, "on", "red"),
        (Generic24KeyCode.GREEN, "on", "green"),
        (Generic24KeyCode.BLUE, "on", "blue"),
        (Generic24KeyCode.WHITE, "on", "white"),
        (Generic24KeyCode.TOMATO, "on", "tomato"),
        (Generic24KeyCode.LIGHT_GREEN, "on", "light_green"),
        (Generic24KeyCode.SKY_BLUE, "on", "sky_blue"),
        (Generic24KeyCode.ORANGE_RED, "on", "orange_red"),
        (Generic24KeyCode.CYAN, "on", "cyan"),
        (Generic24KeyCode.REBECCA_PURPLE, "on", "rebecca_purple"),
        (Generic24KeyCode.ORANGE, "on", "orange"),
        (Generic24KeyCode.TURQUOISE, "on", "turquoise"),
        (Generic24KeyCode.PURPLE, "on", "purple"),
        (Generic24KeyCode.YELLOW, "on", "yellow"),
        (Generic24KeyCode.DARK_CYAN, "on", "dark_cyan"),
        (Generic24KeyCode.PLUM, "on", "plum"),
    ],
    LEDIrDeviceType.GENERIC_40_KEY: [
        (Generic40KeyCode.BRIGHTNESS_UP, STATE_UNKNOWN, None),
        (Generic40KeyCode.BRIGHTNESS_DOWN, STATE_UNKNOWN, None),
        (Generic40KeyCode.WHITE_BRIGHTNESS_UP, STATE_UNKNOWN, None),
        (Generic40KeyCode.WHITE_BRIGHTNESS_DOWN, STATE_UNKNOWN, None),
        (Generic40KeyCode.WHITE_ON, STATE_UNKNOWN, None),
        (Generic40KeyCode.WHITE_OFF, STATE_UNKNOWN, None),
        (Generic40KeyCode.WHITE_BRIGHTNESS_25, STATE_UNKNOWN, None),
        (Generic40KeyCode.WHITE_BRIGHTNESS_50, STATE_UNKNOWN, None),
        (Generic40KeyCode.WHITE_BRIGHTNESS_75, STATE_UNKNOWN, None),
        (Generic40KeyCode.WHITE_BRIGHTNESS_100, STATE_UNKNOWN, None),
        (Generic40KeyCode.QUICK, STATE_UNKNOWN, None),
        (Generic40KeyCode.SLOW, STATE_UNKNOWN, None),
        (Generic40KeyCode.ON, "on", None),
        (Generic40KeyCode.OFF, "off", None),
        (Generic40KeyCode.JUMP3, "on", "jump3"),
        (Generic40KeyCode.JUMP7, "on", "jump7"),
        (Generic40KeyCode.FADE3, "on", "fade3"),
        (Generic40KeyCode.FADE7, "on", "fade7"),
        (Generic40KeyCode.FLASH, "on", "flash"),
        (Generic40KeyCode.AUTO, "on", "auto"),
        (Generic40KeyCode.RED, "on", "red"),
        (Generic40KeyCode.GREEN, "on", "green"),
        (Generic40KeyCode.BLUE, "on", "blue"),
        (Generic40KeyCode.WHITE, "on", "white"),
        (Generic40KeyCode.TOMATO, "on", "tomato"),
        (Generic40KeyCode.LIGHT_GREEN, "on", "light_green"),
        (Generic40KeyCode.DEEP_BLUE, "on", "deep_blue"),
        (Generic40KeyCode.FLORAL_WHITE, "on", "floral_white"),
        (Generic40KeyCode.ORANGE, "on", "orange"),
        (Generic40KeyCode.TURQUOISE, "on", "turquoise"),
        (Generic40KeyCode.PURPLE, "on", "purple"),
        (Generic40KeyCode.LAVENDER_BLUSH, "on", "lavender_blush"),
        (Generic40KeyCode.YELLOWISH, "on", "yellowish"),
        (Generic40KeyCode.CYAN, "on", "cyan"),
        (Generic40KeyCode.MAGENTA, "on", "magenta"),
        (Generic40KeyCode.GHOST_WHITE, "on", "ghost_white"),
        (Generic40KeyCode.YELLOW, "on", "yellow"),
        (Generic40KeyCode.AQUA, "on", "aqua"),
        (Generic40KeyCode.PINK, "on", "pink"),
        (Generic40KeyCode.LIGHT_CYAN, "on", "light_cyan"),
    ],
    LEDIrDeviceType.GENERIC_44_KEY: [
        (Generic44KeyCode.BRIGHTNESS_UP, STATE_UNKNOWN, None),
        (Generic44KeyCode.BRIGHTNESS_DOWN, STATE_UNKNOWN, None),
        (Generic44KeyCode.RED_UP, STATE_UNKNOWN, None),
        (Generic44KeyCode.GREEN_UP, STATE_UNKNOWN, None),
        (Generic44KeyCode.BLUE_UP, STATE_UNKNOWN, None),
        (Generic44KeyCode.RED_DOWN, STATE_UNKNOWN, None),
        (Generic44KeyCode.GREEN_DOWN, STATE_UNKNOWN, None),
        (Generic44KeyCode.BLUE_DOWN, STATE_UNKNOWN, None),
        (Generic44KeyCode.QUICK, STATE_UNKNOWN, None),
        (Generic44KeyCode.SLOW, STATE_UNKNOWN, None),
        (Generic44KeyCode.ON, "on", None),
        (Generic44KeyCode.OFF, "off", None),
        (Generic44KeyCode.DIY1, "on", "diy1"),
        (Generic44KeyCode.DIY2, "on", "diy2"),
        (Generic44KeyCode.DIY3, "on", "diy3"),
        (Generic44KeyCode.DIY4, "on", "diy4"),
        (Generic44KeyCode.DIY5, "on", "diy5"),
        (Generic44KeyCode.DIY6, "on", "diy6"),
        (Generic44KeyCode.AUTO, "on", "auto"),
        (Generic44KeyCode.FLASH, "on", "flash"),
        (Generic44KeyCode.JUMP3, "on", "jump3"),
        (Generic44KeyCode.JUMP7, "on", "jump7"),
        (Generic44KeyCode.FADE3, "on", "fade3"),
        (Generic44KeyCode.FADE7, "on", "fade7"),
        (Generic44KeyCode.RED, "on", "red"),
        (Generic44KeyCode.GREEN, "on", "green"),
        (Generic44KeyCode.BLUE, "on", "blue"),
        (Generic44KeyCode.WHITE, "on", "white"),
        (Generic44KeyCode.TOMATO, "on", "tomato"),
        (Generic44KeyCode.LIGHT_GREEN, "on", "light_green"),
        (Generic44KeyCode.DEEP_BLUE, "on", "deep_blue"),
        (Generic44KeyCode.FLORAL_WHITE, "on", "floral_white"),
        (Generic44KeyCode.ORANGE, "on", "orange"),
        (Generic44KeyCode.TURQUOISE, "on", "turquoise"),
        (Generic44KeyCode.PURPLE, "on", "purple"),
        (Generic44KeyCode.LAVENDER_BLUSH, "on", "lavender_blush"),
        (Generic44KeyCode.YELLOWISH, "on", "yellowish"),
        (Generic44KeyCode.CYAN, "on", "cyan"),
        (Generic44KeyCode.MAGENTA, "on", "magenta"),
        (Generic44KeyCode.GHOST_WHITE, "on", "ghost_white"),
        (Generic44KeyCode.YELLOW, "on", "yellow"),
        (Generic44KeyCode.AQUA, "on", "aqua"),
        (Generic44KeyCode.PINK, "on", "pink"),
        (Generic44KeyCode.LIGHT_CYAN, "on", "light_cyan"),
    ],
}


@pytest.mark.parametrize("device_type", list(_RECEIVED_COMMANDS))
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
@pytest.mark.freeze_time("2026-01-01T13:12:00.000+00:00")
async def test_event(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    device_type: LEDIrDeviceType,
) -> None:
    """Test received command events."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="LED Infrared via Test IR emitter",
        entry_id="1234567890",
        data={
            CONF_DEVICE_TYPE: device_type,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
            CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID,
        },
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get(EVENT_ENTITY_ID))
    assert state.state == STATE_UNKNOWN

    # The event entity keeps its timestamps strictly increasing, so a later
    # timestamp is what shows a command fired an event of its own.
    previous_triggered = dt_util.utcnow() - timedelta(milliseconds=1)

    for command_code, expected_light_state, expected_light_effect in _RECEIVED_COMMANDS[
        device_type
    ]:
        command = command_code.to_command()
        mock_infrared_receiver_entity._handle_received_signal(
            InfraredReceivedSignal(timings=command.get_raw_timings())
        )

        assert (state := hass.states.get(EVENT_ENTITY_ID))
        assert (
            state.attributes[EventEntityStateAttribute.EVENT_TYPE]
            == command_code.name.lower()
        )
        assert (triggered := dt_util.parse_datetime(state.state))
        assert triggered > previous_triggered
        previous_triggered = triggered

        assert (state := hass.states.get(LIGHT_ENTITY_ID))
        assert state.state == expected_light_state
        assert (
            state.attributes[LightEntityStateAttribute.EFFECT] == expected_light_effect
        )


@pytest.mark.parametrize(
    "command",
    [
        NECCommand(address=0x1234, command=0x01),
        NECCommand(address=0x1234, command=0x69),
    ],
)
@pytest.mark.freeze_time("2026-01-01T13:12:00.000+00:00")
async def test_event_unknown_commands(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    config_entry: MockConfigEntry,
    command: NECCommand,
) -> None:
    """Test unknown command events."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=command.get_raw_timings())
    )

    assert (
        state := hass.states.get(
            "event.led_infrared_via_test_ir_emitter_received_command"
        )
    )
    assert state.attributes[EventEntityStateAttribute.EVENT_TYPE] is None
    assert state.state == STATE_UNKNOWN


@pytest.mark.freeze_time("2026-01-01T13:12:00.000+00:00")
async def test_event_non_nec_commands(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    config_entry: MockConfigEntry,
) -> None:
    """Test unknown command events."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=[1, 2, 3, 4])
    )

    assert (
        state := hass.states.get(
            "event.led_infrared_via_test_ir_emitter_received_command"
        )
    )
    assert state.attributes[EventEntityStateAttribute.EVENT_TYPE] is None
    assert state.state == STATE_UNKNOWN
