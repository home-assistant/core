"""Tests for Broadlink infrared platform."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from itertools import chain, repeat
from unittest.mock import call, patch

from broadlink.exceptions import BroadlinkException, ReadError, StorageError
from broadlink.remote import pulses_to_data
from freezegun.api import FrozenDateTimeFactory
from infrared_protocols.commands.nec import NECCommand
import pytest

from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.broadlink.infrared import REARM_INTERVAL
from homeassistant.components.infrared import (
    InfraredReceivedSignal,
    async_send_command,
    async_subscribe_receiver,
)
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from . import MockSetup, get_device

IR_DEVICES = ["Entrance", "Living Room", "Office", "Garage"]
NON_IR_DEVICE = "Bedroom"
DEVICE_NAME = "Entrance"
INFRARED_MODULE = "homeassistant.components.broadlink.infrared"
MALFORMED_PACKET = b"\x26\x00\x03\x00\x00\x01"


def _infrared_entity_id(entity_registry: er.EntityRegistry, suffix: str) -> str:
    """Return the entity id of the emitter or receiver of the test device."""
    entity_id = entity_registry.async_get_entity_id(
        Platform.INFRARED, DOMAIN, f"{get_device(DEVICE_NAME).mac}-{suffix}"
    )
    assert entity_id
    return entity_id


def _nec_packet(command: NECCommand) -> bytes:
    """Encode a NEC command the way a Broadlink device reports a capture."""
    return pulses_to_data([abs(timing) for timing in command.get_raw_timings()])


def _raise(error: Exception) -> None:
    """Raise the given error from within a lambda."""
    raise error


async def _wait_until(predicate: Callable[[], bool]) -> None:
    """Yield to the event loop until the predicate holds."""
    async with asyncio.timeout(10):
        while not predicate():
            await asyncio.sleep(0)


async def _settle() -> None:
    """Give background work a chance to run to completion."""
    for _ in range(50):
        await asyncio.sleep(0)


async def test_infrared_setup_works(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the infrared entities are created for all IR-capable devices."""
    for device in map(get_device, IR_DEVICES):
        mock_setup = await device.setup_entry(hass)

        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, mock_setup.entry.unique_id)}
        )
        entries = er.async_entries_for_device(entity_registry, device_entry.id)
        infrared_entities = [
            entry for entry in entries if entry.domain == Platform.INFRARED
        ]
        assert {entry.unique_id for entry in infrared_entities} == {
            f"{device.mac}-emitter",
            f"{device.mac}-receiver",
        }


async def test_infrared_not_created_for_non_ir_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no infrared entity is created for non-IR devices."""
    device = get_device(NON_IR_DEVICE)
    mock_setup = await device.setup_entry(hass)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_setup.entry.entry_id
    )
    infrared_entities = [
        entry for entry in entries if entry.domain == Platform.INFRARED
    ]
    assert len(infrared_entities) == 0


async def test_infrared_send_command(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sending an IR command dispatches to the Broadlink API."""
    device = get_device("Entrance")
    mock_setup = await device.setup_entry(hass)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_setup.entry.entry_id
    )
    infrared_entity = next(
        entry for entry in entries if entry.domain == Platform.INFRARED
    )

    command = NECCommand(address=0x20, command=0x10)
    await async_send_command(hass, infrared_entity.entity_id, command)

    expected_pulses = [abs(t) for t in command.get_raw_timings()]
    expected_packet = pulses_to_data(expected_pulses)

    assert mock_setup.api.send_data.call_count == 1
    assert mock_setup.api.send_data.call_args == call(expected_packet)


@pytest.mark.parametrize("error", [BroadlinkException("boom"), OSError("boom")])
async def test_infrared_send_command_error_translates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    error: Exception,
) -> None:
    """Test that Broadlink API errors translate to HomeAssistantError."""
    device = get_device("Entrance")
    mock_setup = await device.setup_entry(hass)
    mock_setup.api.send_data.side_effect = error

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_setup.entry.entry_id
    )
    infrared_entity = next(
        entry for entry in entries if entry.domain == Platform.INFRARED
    )

    command = NECCommand(address=0x20, command=0x10)
    with pytest.raises(HomeAssistantError) as exc_info:
        await async_send_command(hass, infrared_entity.entity_id, command)

    assert exc_info.value.translation_key == "send_command_failed"
    assert exc_info.value.translation_domain == DOMAIN


async def test_infrared_receiver_idle_without_subscribers(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the device is not armed while nothing is listening."""
    mock_setup = await get_device(DEVICE_NAME).setup_entry(hass)
    entity_id = _infrared_entity_id(entity_registry, "receiver")

    await hass.async_block_till_done()

    assert mock_setup.api.enter_learning.call_count == 0
    assert mock_setup.api.check_data.call_count == 0

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "preceding_responses",
    [
        pytest.param([], id="captured_immediately"),
        pytest.param([ReadError()], id="after_read_error"),
        pytest.param([StorageError()], id="after_storage_error"),
        pytest.param([MALFORMED_PACKET], id="after_malformed_packet"),
    ],
)
async def test_infrared_receiver_reports_captured_signal(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    preceding_responses: list[bytes | Exception],
) -> None:
    """Test a captured code is reported to subscribers as a received signal."""
    mock_setup = await get_device(DEVICE_NAME).setup_entry(hass)
    entity_id = _infrared_entity_id(entity_registry, "receiver")

    command = NECCommand(address=0x20, command=0x10)
    mock_setup.api.check_data.side_effect = chain(
        preceding_responses, [_nec_packet(command)], repeat(ReadError())
    )

    signals: list[InfraredReceivedSignal] = []
    received = asyncio.Event()

    @callback
    def handle_signal(signal: InfraredReceivedSignal) -> None:
        signals.append(signal)
        received.set()

    with patch(f"{INFRARED_MODULE}.POLL_INTERVAL", 0):
        unsubscribe = async_subscribe_receiver(hass, entity_id, handle_signal)
        async with asyncio.timeout(10):
            await received.wait()
        unsubscribe()

    assert mock_setup.api.enter_learning.call_count >= 1
    assert len(signals) == 1

    timings = signals[0].timings
    assert timings[0] > 0
    assert timings[1] < 0

    # The device quantizes durations to its own tick, so compare the decode of
    # the captured timings against the decode of the timings we encoded.
    decoded = NECCommand.from_raw_timings(timings)
    expected = NECCommand.from_raw_timings(command.get_raw_timings())
    assert decoded is not None
    assert expected is not None
    assert (decoded.address, decoded.command) == (expected.address, expected.command)

    state = hass.states.get(entity_id)
    assert state
    assert dt_util.parse_datetime(state.state) is not None


async def test_infrared_receiver_rearms_after_capture(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a new learning session is started once a capture consumed one."""
    mock_setup = await get_device(DEVICE_NAME).setup_entry(hass)
    entity_id = _infrared_entity_id(entity_registry, "receiver")

    command = NECCommand(address=0x20, command=0x10)
    mock_setup.api.check_data.side_effect = chain(
        [_nec_packet(command)], repeat(ReadError())
    )

    with patch(f"{INFRARED_MODULE}.POLL_INTERVAL", 0):
        unsubscribe = async_subscribe_receiver(hass, entity_id, lambda signal: None)
        await _wait_until(lambda: mock_setup.api.enter_learning.call_count >= 2)
        unsubscribe()


async def test_infrared_receiver_rearms_before_learning_times_out(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the learning session is renewed before the device drops it."""
    mock_setup = await get_device(DEVICE_NAME).setup_entry(hass)
    entity_id = _infrared_entity_id(entity_registry, "receiver")

    mock_setup.api.check_data.side_effect = ReadError

    with patch(f"{INFRARED_MODULE}.POLL_INTERVAL", 0):
        unsubscribe = async_subscribe_receiver(hass, entity_id, lambda signal: None)
        await _wait_until(lambda: mock_setup.api.enter_learning.call_count == 1)

        # The session stays valid, so polling alone must not re-arm the device.
        await _wait_until(lambda: mock_setup.api.check_data.call_count >= 5)
        assert mock_setup.api.enter_learning.call_count == 1

        freezer.tick(REARM_INTERVAL + timedelta(seconds=1))
        await _wait_until(lambda: mock_setup.api.enter_learning.call_count == 2)
        unsubscribe()


async def test_infrared_receiver_discards_own_transmission(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the code a device captures from its own transmission is dropped."""
    mock_setup = await get_device(DEVICE_NAME).setup_entry(hass)
    receiver_id = _infrared_entity_id(entity_registry, "receiver")
    emitter_id = _infrared_entity_id(entity_registry, "emitter")

    sent_command = NECCommand(address=0x20, command=0x10)
    remote_command = NECCommand(address=0x20, command=0x11)

    # Model the device: it captures whatever it sees, arming clears the buffer,
    # and a capture is only readable once.
    captured: list[bytes] = []
    mock_setup.api.enter_learning.side_effect = captured.clear
    mock_setup.api.send_data.side_effect = captured.append
    mock_setup.api.check_data.side_effect = lambda: (
        captured.pop() if captured else _raise(ReadError())
    )

    signals: list[InfraredReceivedSignal] = []

    with (
        patch(f"{INFRARED_MODULE}.POLL_INTERVAL", 0),
        patch(f"{INFRARED_MODULE}.TRANSMIT_COOLDOWN", 0),
    ):
        unsubscribe = async_subscribe_receiver(hass, receiver_id, signals.append)
        await _wait_until(lambda: mock_setup.api.enter_learning.call_count == 1)

        await async_send_command(hass, emitter_id, sent_command)
        await _wait_until(lambda: mock_setup.api.enter_learning.call_count == 2)
        await _wait_until(lambda: mock_setup.api.check_data.call_count >= 3)

        assert signals == []

        # The receiver still reports a code that came from an actual remote.
        captured.append(_nec_packet(remote_command))
        await _wait_until(lambda: len(signals) == 1)
        unsubscribe()

    assert mock_setup.api.send_data.call_count == 1

    decoded = NECCommand.from_raw_timings(signals[0].timings)
    assert decoded is not None
    assert decoded.command == remote_command.command


@pytest.mark.parametrize("error", [BroadlinkException("boom"), OSError("boom")])
async def test_infrared_receiver_recovers_from_errors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    error: Exception,
) -> None:
    """Test the receiver keeps listening after a device error."""
    mock_setup = await get_device(DEVICE_NAME).setup_entry(hass)
    entity_id = _infrared_entity_id(entity_registry, "receiver")

    mock_setup.api.enter_learning.side_effect = chain([error], repeat(None))
    mock_setup.api.check_data.side_effect = ReadError

    with (
        patch(f"{INFRARED_MODULE}.POLL_INTERVAL", 0),
        patch(f"{INFRARED_MODULE}.ERROR_BACKOFF", 0),
    ):
        unsubscribe = async_subscribe_receiver(hass, entity_id, lambda signal: None)
        await _wait_until(lambda: mock_setup.api.check_data.call_count >= 1)
        unsubscribe()

    assert mock_setup.api.enter_learning.call_count >= 2


async def test_infrared_receiver_stops_when_unsubscribed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the device is left alone once nothing is listening anymore."""
    mock_setup = await get_device(DEVICE_NAME).setup_entry(hass)
    entity_id = _infrared_entity_id(entity_registry, "receiver")

    mock_setup.api.check_data.side_effect = ReadError

    with patch(f"{INFRARED_MODULE}.POLL_INTERVAL", 0):
        unsubscribe = async_subscribe_receiver(hass, entity_id, lambda signal: None)
        await _wait_until(lambda: mock_setup.api.check_data.call_count >= 1)
        unsubscribe()

        # The listener finishes the request it is in before it stops.
        await _settle()
        polls_when_unsubscribed = mock_setup.api.check_data.call_count
        await _settle()

    assert mock_setup.api.check_data.call_count == polls_when_unsubscribed


async def test_infrared_receiver_listens_until_last_subscriber_leaves(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the device stays armed once, until the last subscriber is gone."""
    mock_setup = await get_device(DEVICE_NAME).setup_entry(hass)
    entity_id = _infrared_entity_id(entity_registry, "receiver")

    mock_setup.api.check_data.side_effect = ReadError

    with patch(f"{INFRARED_MODULE}.POLL_INTERVAL", 0):
        unsubscribe_first = async_subscribe_receiver(
            hass, entity_id, lambda signal: None
        )
        unsubscribe_second = async_subscribe_receiver(
            hass, entity_id, lambda signal: None
        )
        await _wait_until(lambda: mock_setup.api.check_data.call_count >= 1)

        unsubscribe_first()
        polls_with_one_left = mock_setup.api.check_data.call_count
        await _wait_until(
            lambda: mock_setup.api.check_data.call_count > polls_with_one_left
        )

        unsubscribe_second()
        await _settle()
        polls_when_unsubscribed = mock_setup.api.check_data.call_count
        await _settle()

    # The second subscriber must not start a second listener.
    assert mock_setup.api.enter_learning.call_count == 1
    assert mock_setup.api.check_data.call_count == polls_when_unsubscribed


async def test_infrared_receiver_ignores_repeated_unsubscribe(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test unsubscribing twice does not leave a listener without subscribers."""
    mock_setup = await get_device(DEVICE_NAME).setup_entry(hass)
    entity_id = _infrared_entity_id(entity_registry, "receiver")

    mock_setup.api.check_data.side_effect = ReadError

    with patch(f"{INFRARED_MODULE}.POLL_INTERVAL", 0):
        unsubscribe = async_subscribe_receiver(hass, entity_id, lambda signal: None)
        await _wait_until(lambda: mock_setup.api.check_data.call_count >= 1)

        unsubscribe()
        unsubscribe()
        await _settle()
        polls_when_unsubscribed = mock_setup.api.check_data.call_count
        await _settle()

    assert mock_setup.api.check_data.call_count == polls_when_unsubscribed


async def test_infrared_receiver_stops_on_unload(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test unloading the config entry stops the listener."""
    mock_setup: MockSetup = await get_device(DEVICE_NAME).setup_entry(hass)
    entity_id = _infrared_entity_id(entity_registry, "receiver")

    mock_setup.api.check_data.side_effect = ReadError

    with patch(f"{INFRARED_MODULE}.POLL_INTERVAL", 0):
        async_subscribe_receiver(hass, entity_id, lambda signal: None)
        await _wait_until(lambda: mock_setup.api.check_data.call_count >= 1)

        assert await hass.config_entries.async_unload(mock_setup.entry.entry_id)
        await hass.async_block_till_done()

        polls_when_unloaded = mock_setup.api.check_data.call_count
        await _settle()

    assert mock_setup.api.check_data.call_count == polls_when_unloaded
