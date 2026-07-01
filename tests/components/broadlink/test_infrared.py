"""Tests for Broadlink infrared platform."""

from unittest.mock import call

from broadlink.exceptions import BroadlinkException, ReadError
from broadlink.remote import pulses_to_data
from freezegun.api import FrozenDateTimeFactory
from infrared_protocols.commands.nec import NECCommand
import pytest

from homeassistant.components.broadlink import infrared as broadlink_infrared
from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.infrared import (
    InfraredReceivedSignal,
    async_send_command,
    async_subscribe_receiver,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import get_device

from tests.common import async_fire_time_changed

IR_DEVICES = ["Entrance", "Living Room", "Office", "Garage"]
NON_IR_DEVICE = "Bedroom"


async def test_infrared_setup_works(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the infrared entity is created for all IR-capable devices."""
    for device in map(get_device, IR_DEVICES):
        mock_setup = await device.setup_entry(hass)

        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, mock_setup.entry.unique_id)}
        )
        entries = er.async_entries_for_device(entity_registry, device_entry.id)
        infrared_entities = [
            entry for entry in entries if entry.domain == Platform.INFRARED
        ]
        assert len(infrared_entities) == 2
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
    infrared_emitter_entity = next(
        entry
        for entry in entries
        if entry.domain == Platform.INFRARED and entry.unique_id.endswith("-emitter")
    )

    command = NECCommand(address=0x20, command=0x10)
    await async_send_command(hass, infrared_emitter_entity.entity_id, command)

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
    infrared_emitter_entity = next(
        entry
        for entry in entries
        if entry.domain == Platform.INFRARED and entry.unique_id.endswith("-emitter")
    )

    command = NECCommand(address=0x20, command=0x10)
    with pytest.raises(HomeAssistantError) as exc_info:
        await async_send_command(hass, infrared_emitter_entity.entity_id, command)

    assert exc_info.value.translation_key == "send_command_failed"
    assert exc_info.value.translation_domain == DOMAIN


async def test_infrared_receiver_polling_decodes_and_dispatches_packet(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test polling reads a packet, decodes it, and dispatches receiver callbacks."""
    device = get_device("Entrance")
    mock_setup = await device.setup_entry(hass)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_setup.entry.entry_id
    )
    receiver_entry = next(
        entry
        for entry in entries
        if entry.domain == Platform.INFRARED and entry.unique_id.endswith("-receiver")
    )

    received_signals: list[InfraredReceivedSignal] = []
    async_subscribe_receiver(hass, receiver_entry.entity_id, received_signals.append)
    await hass.async_block_till_done()

    mock_setup.api.reset_mock()
    mock_setup.api.check_data.return_value = b"&\x00\x03\x00\x0f\x15\x1b"

    freezer.tick(broadlink_infrared.LEARNING_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_setup.api.mock_calls == [call.enter_learning(), call.check_data()]
    assert received_signals == [
        InfraredReceivedSignal(timings=[492, -689, 886], modulation=None)
    ]


async def test_infrared_receiver_polling_starts_on_subscribe_and_stops_on_unsubscribe(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test polling is activated by subscription and stopped after unsubscribe."""
    device = get_device("Entrance")
    mock_setup = await device.setup_entry(hass)

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_setup.entry.entry_id
    )
    receiver_entry = next(
        entry
        for entry in entries
        if entry.domain == Platform.INFRARED and entry.unique_id.endswith("-receiver")
    )

    mock_setup.api.check_data.return_value = b"&\x00\x03\x00\x0f\x15\x1b"

    freezer.tick(broadlink_infrared.LEARNING_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    received_signals: list[InfraredReceivedSignal] = []
    unsub = async_subscribe_receiver(
        hass,
        receiver_entry.entity_id,
        received_signals.append,
    )
    await hass.async_block_till_done()

    mock_setup.api.reset_mock()
    freezer.tick(broadlink_infrared.LEARNING_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_setup.api.mock_calls.index(
        call.enter_learning()
    ) < mock_setup.api.mock_calls.index(call.check_data())
    assert received_signals == [
        InfraredReceivedSignal(timings=[492, -689, 886], modulation=None)
    ]

    unsub()
    await hass.async_block_till_done()
    mock_setup.api.reset_mock()

    freezer.tick(broadlink_infrared.LEARNING_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert mock_setup.api.mock_calls == []


async def test_infrared_receiver_polling_logs_enter_learning_failure(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a BroadlinkException in enter_learning is logged and poll continues."""
    device = get_device("Entrance")
    mock_setup = await device.setup_entry(hass)
    mock_setup.api.enter_learning.side_effect = BroadlinkException("no learn")

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_setup.entry.entry_id
    )
    receiver_entry = next(
        entry
        for entry in entries
        if entry.domain == Platform.INFRARED and entry.unique_id.endswith("-receiver")
    )

    async_subscribe_receiver(hass, receiver_entry.entity_id, lambda _: None)
    await hass.async_block_till_done()

    mock_setup.api.reset_mock()
    freezer.tick(broadlink_infrared.LEARNING_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_setup.api.check_data.call_count == 0
    assert "Failed to start infrared receive mode" in caplog.text
    assert receiver_entry.entity_id in caplog.text


async def test_infrared_receiver_logs_decode_failure(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a ValueError from _bl_data_to_pulses is logged and no signal is dispatched."""
    device = get_device("Entrance")
    mock_setup = await device.setup_entry(hass)
    mock_setup.api.check_data.return_value = b"bad"

    monkeypatch.setattr(
        broadlink_infrared,
        "_bl_data_to_pulses",
        lambda _: (_ for _ in ()).throw(ValueError("bad packet")),
    )

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_setup.entry.entry_id
    )
    receiver_entry = next(
        entry
        for entry in entries
        if entry.domain == Platform.INFRARED and entry.unique_id.endswith("-receiver")
    )

    received_signals: list[InfraredReceivedSignal] = []
    async_subscribe_receiver(hass, receiver_entry.entity_id, received_signals.append)
    await hass.async_block_till_done()

    mock_setup.api.reset_mock()
    freezer.tick(broadlink_infrared.LEARNING_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert received_signals == []
    assert "Failed to decode infrared signal packet" in caplog.text


async def test_infrared_receiver_polling_ignores_read_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that ReadError from check_data results in no signal being dispatched."""
    device = get_device("Entrance")
    mock_setup = await device.setup_entry(hass)
    mock_setup.api.check_data.side_effect = ReadError()

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_setup.entry.entry_id
    )
    receiver_entry = next(
        entry
        for entry in entries
        if entry.domain == Platform.INFRARED and entry.unique_id.endswith("-receiver")
    )

    received_signals: list[InfraredReceivedSignal] = []
    async_subscribe_receiver(hass, receiver_entry.entity_id, received_signals.append)
    await hass.async_block_till_done()

    mock_setup.api.reset_mock()
    freezer.tick(broadlink_infrared.LEARNING_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert received_signals == []
