"""Tests for the SilverCrest Infrared event platform."""

from collections.abc import Generator
from unittest.mock import patch

from infrared_protocols.codes.silvercrest.fan import SilverCrestFanCode
from infrared_protocols.commands.symphony import SymphonyCommand, SymphonyKey
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.components.infrared.common import MockInfraredReceiverEntity
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import EventEntityStateAttribute
from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

EVENT_ENTITY_ID = "event.misting_pedestal_fan_ssvs_85_a1_received_command"


@pytest.fixture(autouse=True)
def event_only() -> Generator[None]:
    """Enable only the event platform."""
    with patch(
        "homeassistant.components.silvercrest_infrared.PLATFORMS",
        [Platform.EVENT],
    ):
        yield


@pytest.mark.usefixtures("mock_infrared_receiver_entity")
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
    "command_code",
    [
        pytest.param(SilverCrestFanCode.MODE, id="mode"),
        pytest.param(SilverCrestFanCode.OSC, id="osc"),
        pytest.param(SilverCrestFanCode.POWER, id="power"),
        pytest.param(SilverCrestFanCode.SPEED, id="speed"),
        pytest.param(SilverCrestFanCode.TIMER, id="timer"),
    ],
)
@pytest.mark.usefixtures(
    "mock_infrared_emitter_entity", "mock_infrared_receiver_entity"
)
@pytest.mark.freeze_time("2026-01-01T13:12:00.000+00:00")
async def test_event(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    config_entry: MockConfigEntry,
    command_code: SilverCrestFanCode,
) -> None:
    """Test received command events."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get(EVENT_ENTITY_ID))
    assert state.state == STATE_UNKNOWN

    command = command_code.to_command()
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=command.get_raw_timings())
    )

    assert (state := hass.states.get(EVENT_ENTITY_ID))
    assert state.state == "2026-01-01T13:12:00.000+00:00"
    assert (
        state.attributes[EventEntityStateAttribute.EVENT_TYPE]
        == command_code.name.lower()
    )


@pytest.mark.parametrize(
    "command",
    [
        SymphonyCommand(custom_code=0, control_word=SymphonyKey.K1),
        SymphonyCommand(custom_code=0, control_word=SymphonyKey.K8),
    ],
)
@pytest.mark.freeze_time("2026-01-01T13:12:00.000+00:00")
async def test_event_unknown_commands(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    config_entry: MockConfigEntry,
    command: SymphonyCommand,
) -> None:
    """Test unknown command events."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=command.get_raw_timings())
    )

    assert (state := hass.states.get(EVENT_ENTITY_ID))
    assert state.attributes[EventEntityStateAttribute.EVENT_TYPE] is None
    assert state.state == STATE_UNKNOWN


@pytest.mark.freeze_time("2026-01-01T13:12:00.000+00:00")
async def test_event_non_symphony_commands(
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

    assert (state := hass.states.get(EVENT_ENTITY_ID))
    assert state.attributes[EventEntityStateAttribute.EVENT_TYPE] is None
    assert state.state == STATE_UNKNOWN
