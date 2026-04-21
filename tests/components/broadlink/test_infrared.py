"""Tests for Broadlink infrared platform."""

from broadlink.remote import data_to_pulses
from infrared_protocols import NECCommand
import pytest

from homeassistant.components import infrared
from homeassistant.components.broadlink.const import DOMAIN, IR_PACKET_REPEAT_INDEX
from homeassistant.components.broadlink.infrared import BroadlinkIRCommand
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import BroadlinkDevice, MockSetup, get_device

IR_DEVICES = ["Entrance", "Living Room", "Office", "Garage"]

# IR data packet type byte emitted by Broadlink devices
IR_PACKET_TYPE = 0x26


async def _setup_ir_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device: BroadlinkDevice,
) -> tuple[MockSetup, str]:
    """Set up a Broadlink device and return its infrared entity id."""
    mock_setup = await device.setup_entry(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    ir_entries = [entry for entry in entries if entry.domain == Platform.INFRARED]
    assert len(ir_entries) == 1
    return mock_setup, ir_entries[0].entity_id


async def test_infrared_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the infrared entity is created for every IR-capable device."""
    for device in map(get_device, IR_DEVICES):
        _, entity_id = await _setup_ir_device(
            hass, device_registry, entity_registry, device
        )
        assert hass.states.get(entity_id) is not None


async def test_send_nec_command(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test sending an NECCommand transmits a single-shot Broadlink IR packet."""
    mock_setup, entity_id = await _setup_ir_device(
        hass, device_registry, entity_registry, get_device("Entrance")
    )

    await infrared.async_send_command(
        hass, entity_id, NECCommand(address=0x04, command=0x08)
    )

    mock_setup.api.send_data.assert_called_once()
    packet = mock_setup.api.send_data.call_args.args[0]
    # Protocol-aware commands encode repeats inside the timings, so the
    # hardware repeat byte must remain zero to avoid double-repeating.
    assert packet[0] == IR_PACKET_TYPE
    assert packet[IR_PACKET_REPEAT_INDEX] == 0
    # Round-trip decode: the first pulse pair must match the NEC leader.
    pulses = data_to_pulses(packet)
    assert pulses[0] == pytest.approx(9000, abs=50)
    assert pulses[1] == pytest.approx(4500, abs=50)


async def test_send_broadlink_ir_command_uses_hardware_repeat(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test BroadlinkIRCommand's repeat_count maps to the hardware repeat byte."""
    mock_setup, entity_id = await _setup_ir_device(
        hass, device_registry, entity_registry, get_device("Entrance")
    )

    await infrared.async_send_command(
        hass,
        entity_id,
        BroadlinkIRCommand([(9000, 4500), (562, 562)], repeat_count=3),
    )

    mock_setup.api.send_data.assert_called_once()
    packet = mock_setup.api.send_data.call_args.args[0]
    assert packet[IR_PACKET_REPEAT_INDEX] == 3


def test_broadlink_ir_command_repeat_validation() -> None:
    """Test BroadlinkIRCommand rejects repeat counts outside 0-255."""
    with pytest.raises(ValueError, match="repeat_count must be 0–255"):
        BroadlinkIRCommand([(500, 500)], repeat_count=-1)
    with pytest.raises(ValueError, match="repeat_count must be 0–255"):
        BroadlinkIRCommand([(500, 500)], repeat_count=256)

    # Boundary values must succeed.
    BroadlinkIRCommand([(500, 500)], repeat_count=0)
    BroadlinkIRCommand([(500, 500)], repeat_count=255)
