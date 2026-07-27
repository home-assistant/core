"""Tests for the LED Infrared event platform."""

from collections.abc import Generator
from unittest.mock import patch

from infrared_protocols.codes.generic.led import Generic13KeyCode, Generic24KeyCode
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


@pytest.mark.parametrize(
    ("device_type", "command_code", "expected_light_state", "expected_light_effect"),
    [
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.ON, "on", None),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.OFF, "off", None),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            Generic24KeyCode.BRIGHTNESS_UP,
            STATE_UNKNOWN,
            None,
        ),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            Generic24KeyCode.BRIGHTNESS_DOWN,
            STATE_UNKNOWN,
            None,
        ),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.FLASH, "on", "flash"),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.STROBE, "on", "strobe"),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.FADE, "on", "fade"),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.SMOOTH, "on", "smooth"),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.RED, "on", "red"),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.GREEN, "on", "green"),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.BLUE, "on", "blue"),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.WHITE, "on", "white"),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.TOMATO, "on", "tomato"),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            Generic24KeyCode.LIGHT_GREEN,
            "on",
            "light_green",
        ),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.SKY_BLUE, "on", "sky_blue"),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            Generic24KeyCode.ORANGE_RED,
            "on",
            "orange_red",
        ),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.CYAN, "on", "cyan"),
        (
            LEDIrDeviceType.GENERIC_24_KEY,
            Generic24KeyCode.REBECCA_PURPLE,
            "on",
            "rebecca_purple",
        ),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.ORANGE, "on", "orange"),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.TURQUOISE, "on", "turquoise"),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.PURPLE, "on", "purple"),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.YELLOW, "on", "yellow"),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.DARK_CYAN, "on", "dark_cyan"),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.PLUM, "on", "plum"),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.ON, "on", None),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.OFF, "off", None),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.TIMER, STATE_UNKNOWN, None),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_1, "on", "mode_1"),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_2, "on", "mode_2"),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_3, "on", "mode_3"),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_4, "on", "mode_4"),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_5, "on", "mode_5"),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_6, "on", "mode_6"),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_7, "on", "mode_7"),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_8, "on", "mode_8"),
        (
            LEDIrDeviceType.GENERIC_13_KEY,
            Generic13KeyCode.BRIGHTNESS_UP,
            STATE_UNKNOWN,
            None,
        ),
        (
            LEDIrDeviceType.GENERIC_13_KEY,
            Generic13KeyCode.BRIGHTNESS_DOWN,
            STATE_UNKNOWN,
            None,
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
@pytest.mark.freeze_time("2026-01-01T13:12:00.000+00:00")
async def test_event(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    device_type: LEDIrDeviceType,
    command_code: Generic13KeyCode | Generic24KeyCode,
    expected_light_state: str,
    expected_light_effect: str | None,
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

    assert (
        state := hass.states.get(
            "event.led_infrared_via_test_ir_emitter_received_command"
        )
    )
    assert state.state == STATE_UNKNOWN

    command = command_code.to_command()
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=command.get_raw_timings())
    )

    assert (
        state := hass.states.get(
            "event.led_infrared_via_test_ir_emitter_received_command"
        )
    )
    assert (
        state.attributes[EventEntityStateAttribute.EVENT_TYPE]
        == command_code.name.lower()
    )
    assert state.state == "2026-01-01T13:12:00.000+00:00"

    assert (state := hass.states.get("light.led_infrared_via_test_ir_emitter"))
    assert state.state == expected_light_state
    assert state.attributes[LightEntityStateAttribute.EFFECT] == expected_light_effect


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
