"""The tests for the kitchen_sink event platform."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from infrared_protocols.commands.nec import NECCommand
import pytest

from homeassistant import config_entries
from homeassistant.components.event import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES
from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.components.kitchen_sink import DOMAIN
from homeassistant.components.kitchen_sink.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_RECEIVER_ENTITY_ID,
    INFRARED_CMD_POWER_ON,
    INFRARED_FAN_ADDRESS,
)
from homeassistant.components.kitchen_sink.infrared import INFRARED_COMMAND_SIGNAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry
from tests.components.infrared import EMITTER_ENTITY_ID, RECEIVER_ENTITY_ID
from tests.components.infrared.common import (
    MockInfraredReceiverEntity,
    captured_code,
    received_signal,
    seed_commands,
)

ENTITY_RECEIVED_IR_EVENT = "event.living_room_fan_received_ir_event"
ENTITY_INFRARED_COMMAND = "event.ir_blaster_infrared_command"


@pytest.fixture
def event_only() -> Generator[None]:
    """Enable only the event platform."""
    with patch(
        "homeassistant.components.kitchen_sink.COMPONENTS_WITH_DEMO_PLATFORM",
        [Platform.EVENT],
    ):
        yield


@pytest.fixture
async def config_entry(
    hass: HomeAssistant,
    event_only: None,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> MockConfigEntry:
    """Set up a kitchen_sink config entry with the event platform only."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={
                    CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
                    CONF_INFRARED_RECEIVER_ENTITY_ID: RECEIVER_ENTITY_ID,
                },
                subentry_id="living_room_fan",
                subentry_type="infrared_fan",
                title="Living Room Fan",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.usefixtures("config_entry")
async def test_event_receives_signal(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the event entity fires for IR signals from the receiver."""
    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    assert now is not None
    freezer.move_to(now)

    command = NECCommand(
        address=INFRARED_FAN_ADDRESS, command=INFRARED_CMD_POWER_ON, modulation=38000
    )
    raw_timings = command.get_raw_timings()
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=raw_timings)
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_RECEIVED_IR_EVENT)) is not None
    assert state.state == now.isoformat(timespec="milliseconds")
    assert state.attributes[ATTR_EVENT_TYPE] == "power_on"
    assert state.attributes["raw_code"] == raw_timings


@pytest.mark.usefixtures("config_entry")
async def test_event_resubscribes_after_receiver_reload(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the event entity resubscribes after the receiver is reloaded."""
    assert (state := hass.states.get(ENTITY_RECEIVED_IR_EVENT)) is not None
    assert state.state != STATE_UNAVAILABLE

    hass.states.async_set(RECEIVER_ENTITY_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert (state := hass.states.get(ENTITY_RECEIVED_IR_EVENT)) is not None
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set(RECEIVER_ENTITY_ID, STATE_UNKNOWN)
    await hass.async_block_till_done()

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    assert now is not None
    freezer.move_to(now)

    command = NECCommand(
        address=INFRARED_FAN_ADDRESS, command=INFRARED_CMD_POWER_ON, modulation=38000
    )
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=command.get_raw_timings())
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_RECEIVED_IR_EVENT)) is not None
    assert state.state == now.isoformat(timespec="milliseconds")


@pytest.fixture
def infrared_platforms_only() -> Generator[None]:
    """Enable the event and infrared platforms."""
    with patch(
        "homeassistant.components.kitchen_sink.COMPONENTS_WITH_DEMO_PLATFORM",
        [Platform.EVENT, Platform.INFRARED],
    ):
        yield


@pytest.mark.usefixtures("infrared_platforms_only")
async def test_infrared_command_event(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the demo receiver reports the known infrared commands it picks up."""
    command = NECCommand(
        address=INFRARED_FAN_ADDRESS, command=INFRARED_CMD_POWER_ON, modulation=38000
    )
    seed_commands(
        hass_storage, [{"id": "power", "name": "Power", "code": captured_code(command)}]
    )

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_INFRARED_COMMAND)) is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_EVENT_TYPES] == ["Power"]

    now = dt_util.parse_datetime("2021-01-09 12:00:00+00:00")
    assert now is not None
    freezer.move_to(now)
    async_dispatcher_send(
        hass, INFRARED_COMMAND_SIGNAL, received_signal(command).timings
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_INFRARED_COMMAND)) is not None
    assert state.state == now.isoformat(timespec="milliseconds")
    assert state.attributes[ATTR_EVENT_TYPE] == "Power"
    assert state.attributes["command_id"] == "power"
