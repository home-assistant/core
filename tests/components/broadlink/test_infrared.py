"""Tests for Broadlink infrared platform."""

from datetime import datetime
from unittest.mock import call

from broadlink.exceptions import BroadlinkException, ReadError, StorageError
from broadlink.remote import pulses_to_data
from infrared_protocols.commands.nec import NECCommand
import pytest

from homeassistant.components.broadlink import infrared as broadlink_infrared
from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.infrared import (
    DATA_COMPONENT,
    InfraredReceivedSignal,
    InfraredReceiverEntity,
    async_send_command,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.dt import naive_now

from . import get_device

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


@pytest.mark.parametrize(
    ("error", "error_type"),
    [
        pytest.param(BroadlinkException("boom"), BroadlinkException, id="broadlink"),
        pytest.param(OSError("boom"), OSError, id="os"),
        pytest.param(ReadError("boom"), ReadError, id="read"),
        pytest.param(StorageError("boom"), StorageError, id="storage"),
    ],
)
async def test_infrared_receive_command_error_translates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    error: Exception,
    error_type: type[Exception],
) -> None:
    """Test that Broadlink receiver API errors translate to HomeAssistantError."""
    device = get_device("Entrance")
    mock_setup = await device.setup_entry(hass)
    mock_setup.api.check_data.side_effect = error

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_setup.entry.entry_id
    )
    receiver_entry = next(
        entry
        for entry in entries
        if entry.domain == Platform.INFRARED and entry.unique_id.endswith("-receiver")
    )

    receiver = hass.data[DATA_COMPONENT].get_entity(receiver_entry.entity_id)
    assert isinstance(receiver, InfraredReceiverEntity)

    with pytest.raises(HomeAssistantError) as exc_info:
        await receiver._async_poll_received_signal(naive_now())

    assert exc_info.value.translation_key == "receive_command_failed"
    assert exc_info.value.translation_domain == DOMAIN
    assert isinstance(exc_info.value.__cause__, error_type)


@pytest.mark.parametrize("error", [BroadlinkException("boom"), OSError("boom")])
async def test_infrared_poll_enter_learning_error_translates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    error: Exception,
) -> None:
    """Test poll path keeps learning mode translation when learning mode fails."""
    device = get_device("Entrance")
    mock_setup = await device.setup_entry(hass)
    mock_setup.api.enter_learning.side_effect = error

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_setup.entry.entry_id
    )
    receiver_entry = next(
        entry
        for entry in entries
        if entry.domain == Platform.INFRARED and entry.unique_id.endswith("-receiver")
    )

    receiver = hass.data[DATA_COMPONENT].get_entity(receiver_entry.entity_id)
    assert isinstance(receiver, InfraredReceiverEntity)

    with pytest.raises(HomeAssistantError) as exc_info:
        await receiver._async_poll_received_signal(naive_now())

    assert exc_info.value.translation_key == "enter_learning_command_failed"
    assert exc_info.value.translation_domain == DOMAIN


@pytest.mark.parametrize("error", [BroadlinkException("boom"), OSError("boom")])
async def test_infrared_enter_learning_error_translates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    error: Exception,
) -> None:
    """Test that learning mode API errors translate to HomeAssistantError."""
    device = get_device("Entrance")
    mock_setup = await device.setup_entry(hass)
    mock_setup.api.enter_learning.side_effect = error

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_setup.entry.entry_id
    )
    receiver_entry = next(
        entry
        for entry in entries
        if entry.domain == Platform.INFRARED and entry.unique_id.endswith("-receiver")
    )

    receiver = hass.data[DATA_COMPONENT].get_entity(receiver_entry.entity_id)
    assert isinstance(receiver, InfraredReceiverEntity)

    with pytest.raises(HomeAssistantError) as exc_info:
        await receiver._async_enter_learning_mode()

    assert exc_info.value.translation_key == "enter_learning_command_failed"
    assert exc_info.value.translation_domain == DOMAIN


@pytest.mark.parametrize("error_message", ["boom", "bad packet"])
async def test_infrared_decode_signal_error_translates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
    error_message: str,
) -> None:
    """Test that signal decode errors translate to HomeAssistantError."""
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

    receiver = hass.data[DATA_COMPONENT].get_entity(receiver_entry.entity_id)
    assert isinstance(receiver, InfraredReceiverEntity)

    def _raise_decode_error(_: bytes) -> list[int]:
        raise ValueError(error_message)

    monkeypatch.setattr(
        broadlink_infrared,
        "_bl_data_to_pulses",
        _raise_decode_error,
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        receiver._handle_received_ir_signal(b"packet")

    assert exc_info.value.translation_key == "decode_signal_failed"
    assert exc_info.value.translation_domain == DOMAIN


async def test_infrared_receiver_packet_handling(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test receiver decodes a Broadlink packet and dispatches signal callbacks."""
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

    receiver = hass.data[DATA_COMPONENT].get_entity(receiver_entry.entity_id)
    assert isinstance(receiver, InfraredReceiverEntity)

    received_signals: list[InfraredReceivedSignal] = []
    receiver.async_subscribe_received_signal(received_signals.append)

    receiver._handle_received_ir_signal(pulses_to_data([500, 700, 900]))
    await hass.async_block_till_done()

    assert received_signals == [
        InfraredReceivedSignal(timings=[500, -700, 900], modulation=None)
    ]
    state = hass.states.get(receiver_entry.entity_id)
    assert state is not None
    assert datetime.fromisoformat(state.state) is not None
