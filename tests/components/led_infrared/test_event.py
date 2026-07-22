"""Tests for the LED Infrared event platform."""

from collections.abc import Generator
from unittest.mock import patch

from infrared_protocols.codes.generic.led import Generic13KeyCode, Generic24KeyCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import EventEntityStateAttribute
from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.components.led_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    DOMAIN,
    LEDIrDeviceType,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.infrared import RECEIVER_ENTITY_ID
from tests.components.infrared.common import MockInfraredReceiverEntity


@pytest.fixture(autouse=True)
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
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
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
    ("device_type", "command_code"),
    [
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.ON),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.OFF),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.BRIGHTNESS_UP),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.BRIGHTNESS_DOWN),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.FLASH),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.STROBE),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.FADE),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.SMOOTH),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.RED),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.GREEN),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.BLUE),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.WHITE),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.TOMATO),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.LIGHT_GREEN),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.SKY_BLUE),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.ORANGE_RED),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.CYAN),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.REBECCA_PURPLE),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.ORANGE),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.TURQUOISE),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.PURPLE),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.YELLOW),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.DARK_CYAN),
        (LEDIrDeviceType.GENERIC_24_KEY, Generic24KeyCode.PLUM),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.ON),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.OFF),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.TIMER),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_1),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_2),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_3),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_4),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_5),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_6),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_7),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.MODE_8),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.BRIGHTNESS_UP),
        (LEDIrDeviceType.GENERIC_13_KEY, Generic13KeyCode.BRIGHTNESS_DOWN),
    ],
)
@pytest.mark.freeze_time("2026-01-01T13:12:00.000+00:00")
async def test_event(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    device_type: LEDIrDeviceType,
    command_code: Generic13KeyCode | Generic24KeyCode,
) -> None:
    """Test webhook events."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="LED Infrared via Test IR emitter",
        entry_id="1234567890",
        data={
            CONF_DEVICE_TYPE: device_type,
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
