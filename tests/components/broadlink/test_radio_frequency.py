"""Tests for the Broadlink radio_frequency platform."""

from __future__ import annotations

from base64 import b64decode
from unittest.mock import MagicMock, call

from broadlink.exceptions import BroadlinkException
import pytest
from rf_protocols import OOKCommand

from homeassistant.components import radio_frequency
from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.broadlink.radio_frequency import (
    _RF_315_TYPE_BYTE,
    _RF_433_TYPE_BYTE,
    _TICK_US,
    encode_rf_packet,
)
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import get_device

# Real-world learned captures used for the encoder round-trip. Each capture
# starts with the 0xB1 0xC0 learning wrapper, followed by sweep telemetry,
# followed by the actual OOK pulse bytes. The declared payload length field
# ends just inside the capture, so we slice to that length for the round trip.
_PLUS_CAPTURE_B64 = (
    "scDSAACfBgAEAAQDBAAC4PO/DA0WGQsNFxgMDBcYDA0WGQsNFhkLDRcZCwACAAsN"
    "FxcNDBcYDAwXGAwMFxkLDRcYDAwXGAsAAgELDRcYDAwYGAsMGBcNDBcYCw0XGAwM"
    "FxkLAAIADAwYFwwMFxgMDRcYCwwYGAwMFxgMDBgXDAACAAwNFhgMDBgYDAsYGAwM"
    "FxgLDhYZCwwYGAwAAgALDBgXDQwWGQsNFxgMDBcZCwwYFwwNFxgLAAIADA0WGQsM"
    "GBgMDBcXDQwYFwwNFhkLDBgYCwAF3A=="
)
_PLUS_PULSE_START = 18  # end of 14-byte sweep telemetry (00 9f 06 00 ... f3 bf)

_MINUS_CAPTURE_B64 = (
    "scCcAACfBgAGAAFuBC4EUQQ59L8MDBgXDA0WGQsNFxkLDBcYDA0WGAwYCw4WAAIA"
    "DAwYFw0MFhgMDRcYDAwYFwwMGBcNFwsOFgACAAwMGBcMDBgXDA0XGAsNFxgMDBgX"
    "DBgMDBcAAgAMDBcZCwwYFw0MFhkLDRcYDAwXGAwMGBcNFwsOFgACAAwMGBcMDBgX"
    "DA0XGAsNFxgMDBgXDBgMDBcAAgAMDBcZCwwYFw0MFhkLDRcYDAwXGAwMGBcXDQwX"
    "AAIADAwXGAwMGBcNCxgXDQwWGQsNFxgMGAsNFwAF3A=="
)
_MINUS_PULSE_START = 20  # end of 16-byte sweep telemetry (00 9f 06 00 ... f4 bf)

_RF_DEVICES = ["Office", "Garage"]  # RMPRO / RM4PRO
_NON_RF_DEVICES = ["Entrance", "Living Room"]  # RMMINI / RMMINIB

_FREQ_433 = 433_920_000
_FREQ_315 = 315_000_000


def _ticks_to_timings(ticks: list[int]) -> list[int]:
    """Convert Broadlink ticks to signed alternating microseconds.

    Even indices are marks (positive), odd indices are spaces (negative),
    matching the rf_protocols raw-timings convention.
    """
    return [
        round(value * _TICK_US) * (1 if index % 2 == 0 else -1)
        for index, value in enumerate(ticks)
    ]


def _decode_pulse_bytes(pulse_bytes: bytes) -> list[int]:
    """Parse a slice of Broadlink pulse bytes into tick counts."""
    result: list[int] = []
    index = 0
    while index < len(pulse_bytes):
        value = pulse_bytes[index]
        index += 1
        if value == 0:
            value = (pulse_bytes[index] << 8) | pulse_bytes[index + 1]
            index += 2
        result.append(value)
    return result


def _extract_capture(b64: str, pulse_start: int) -> tuple[int, bytes, list[int]]:
    """Return (repeat_count, pulse_bytes, timings_us) from a learned capture."""
    raw = b64decode(b64)
    repeat_count = raw[1]
    payload_len = raw[2] | (raw[3] << 8)
    pulse_bytes = raw[pulse_start : 4 + payload_len]
    ticks = _decode_pulse_bytes(pulse_bytes)
    return repeat_count, pulse_bytes, _ticks_to_timings(ticks)


async def test_radio_frequency_setup_for_rf_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that RF-capable Broadlink devices get a radio_frequency entity."""
    for device in map(get_device, _RF_DEVICES):
        mock_setup = await device.setup_entry(hass)

        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, mock_setup.entry.unique_id)}
        )
        entries = er.async_entries_for_device(entity_registry, device_entry.id)
        rf_entities = [
            entry for entry in entries if entry.domain == Platform.RADIO_FREQUENCY
        ]
        assert len(rf_entities) == 1
        assert rf_entities[0].unique_id == device.mac


async def test_radio_frequency_not_registered_for_non_rf_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that non-RF Broadlink devices don't get a radio_frequency entity."""
    for device in map(get_device, _NON_RF_DEVICES):
        mock_setup = await device.setup_entry(hass)

        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, mock_setup.entry.unique_id)}
        )
        entries = er.async_entries_for_device(entity_registry, device_entry.id)
        rf_entities = [
            entry for entry in entries if entry.domain == Platform.RADIO_FREQUENCY
        ]
        assert rf_entities == []


async def test_encoder_matches_simple_fixture() -> None:
    """Test the encoder against a hand-crafted packet with escape-encoded pulses."""
    # A short, hand-crafted OOK train: one small pulse (12 ticks = 394 µs),
    # one escape-encoded pulse (300 ticks = 9852 µs), then another small one.
    # Ticks: 12, 300, 12 -> bytes: 0x0c, 0x00 0x01 0x2c, 0x0c -> 5 bytes payload.
    timings = [round(12 * _TICK_US), round(300 * _TICK_US), round(12 * _TICK_US)]

    packet = encode_rf_packet(
        type_byte=_RF_433_TYPE_BYTE,
        repeat_count=3,
        timings_us=timings,
    )

    assert packet == bytes([0xB2, 0x03, 0x05, 0x00, 0x0C, 0x00, 0x01, 0x2C, 0x0C])


@pytest.mark.parametrize(
    ("b64", "pulse_start"),
    [
        (_PLUS_CAPTURE_B64, _PLUS_PULSE_START),
        (_MINUS_CAPTURE_B64, _MINUS_PULSE_START),
    ],
    ids=["plus", "minus"],
)
async def test_encoder_round_trips_real_capture(b64: str, pulse_start: int) -> None:
    """Re-encoded transmit payload is byte-identical to the captured pulses.

    The captures start with a 0xB1 0xC0 learning wrapper plus sweep telemetry.
    Strip the telemetry, decode the pulse bytes, feed the resulting timings
    to the encoder with a 0xB2 transmit type byte, and assert the output
    equals the original header + pulses slice.
    """
    repeat_count, pulse_bytes, timings = _extract_capture(b64, pulse_start)

    encoded = encode_rf_packet(
        type_byte=_RF_433_TYPE_BYTE,
        repeat_count=repeat_count,
        timings_us=timings,
    )

    expected = (
        bytes(
            [
                _RF_433_TYPE_BYTE,
                repeat_count,
                len(pulse_bytes) & 0xFF,
                (len(pulse_bytes) >> 8) & 0xFF,
            ]
        )
        + pulse_bytes
    )
    assert encoded == expected


async def test_encoder_uses_315_mhz_type_byte() -> None:
    """A 315 MHz-band encoded packet uses type byte 0xB4."""
    packet = encode_rf_packet(
        type_byte=_RF_315_TYPE_BYTE,
        repeat_count=0,
        timings_us=[round(12 * _TICK_US), round(12 * _TICK_US)],
    )
    assert packet[0] == 0xB4


async def _setup_rf_device(hass: HomeAssistant) -> tuple[MagicMock, str]:
    """Set up a single RF-capable Broadlink device, return its api mock and entity_id."""
    device = get_device("Office")  # RMPRO
    mock_setup = await device.setup_entry(hass)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    rf_entity = next(
        entry for entry in entries if entry.domain == Platform.RADIO_FREQUENCY
    )
    return mock_setup.api, rf_entity.entity_id


async def test_async_send_command_transmits_once(hass: HomeAssistant) -> None:
    """Sending an OOK command invokes send_data once with the encoded packet."""
    api, entity_id = await _setup_rf_device(hass)

    timings = [400, -800, 400, -800]
    command = OOKCommand(frequency=_FREQ_433, timings=timings)
    await radio_frequency.async_send_command(hass, entity_id, command)

    expected_packet = encode_rf_packet(
        type_byte=_RF_433_TYPE_BYTE,
        repeat_count=0,
        timings_us=timings,
    )
    assert api.send_data.call_count == 1
    assert api.send_data.call_args == call(expected_packet)


async def test_async_send_command_uses_315_band(hass: HomeAssistant) -> None:
    """A command on the 315 MHz band produces a packet with type byte 0xB4."""
    api, entity_id = await _setup_rf_device(hass)

    command = OOKCommand(frequency=_FREQ_315, timings=[400, -800])
    await radio_frequency.async_send_command(hass, entity_id, command)

    assert api.send_data.call_count == 1
    sent_packet = api.send_data.call_args.args[0]
    assert sent_packet[0] == _RF_315_TYPE_BYTE


async def test_async_send_command_rejects_unsupported_frequency(
    hass: HomeAssistant,
) -> None:
    """A command outside the two Broadlink bands is rejected before send."""
    api, entity_id = await _setup_rf_device(hass)

    command = OOKCommand(frequency=868_000_000, timings=[400, -800])
    with pytest.raises(HomeAssistantError):
        await radio_frequency.async_send_command(hass, entity_id, command)

    assert api.send_data.call_count == 0


async def test_async_send_command_rejects_non_ook_modulation(
    hass: HomeAssistant,
) -> None:
    """A non-OOK command is rejected before send.

    The public domain ``async_send_command`` short-circuits via
    ``supports_modulation`` before dispatching to the entity, so a
    synthetic non-OOK command still raises ``HomeAssistantError`` and
    ``send_data`` is never called.
    """
    api, entity_id = await _setup_rf_device(hass)

    command = OOKCommand(frequency=_FREQ_433, timings=[400, -800])
    # Bypass the StrEnum to simulate a hypothetical future modulation.
    command.modulation = "FSK"

    with pytest.raises(HomeAssistantError):
        await radio_frequency.async_send_command(hass, entity_id, command)

    assert api.send_data.call_count == 0


async def test_async_send_command_transmit_failure_raises(
    hass: HomeAssistant,
) -> None:
    """A broadlink exception from send_data surfaces as HomeAssistantError."""
    api, entity_id = await _setup_rf_device(hass)

    api.send_data.side_effect = BroadlinkException("nope")

    command = OOKCommand(frequency=_FREQ_433, timings=[400, -800])
    with pytest.raises(HomeAssistantError):
        await radio_frequency.async_send_command(hass, entity_id, command)


async def test_radio_frequency_entity_availability(hass: HomeAssistant) -> None:
    """The entity is unavailable when the underlying device is unavailable."""
    device = get_device("Office")
    mock_setup = await device.setup_entry(hass)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    rf_entity = next(
        entry for entry in entries if entry.domain == Platform.RADIO_FREQUENCY
    )

    state = hass.states.get(rf_entity.entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    # Force the coordinator into a failed state and trigger a refresh.
    broadlink_device = hass.data[DOMAIN].devices[mock_setup.entry.entry_id]
    broadlink_device.update_manager.available = False
    broadlink_device.update_manager.coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(rf_entity.entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
