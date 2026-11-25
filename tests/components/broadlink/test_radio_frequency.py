"""Tests for the Broadlink radio_frequency platform."""

from datetime import timedelta
from unittest.mock import MagicMock, call

from broadlink_async.exceptions import BroadlinkException
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from rf_protocols.commands.ook import OOKCommand

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
from homeassistant.util import dt as dt_util

from . import get_device

_FREQ_433 = 433_920_000
_FREQ_315 = 315_000_000


async def _setup_rf_device(
    hass: HomeAssistant, device_name: str = "Office"
) -> tuple[MagicMock, str]:
    """Set up a test device (RMPRO by default), return its api mock and RF entity_id."""
    device = get_device(device_name)
    mock_setup = await device.setup_entry(hass)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_setup.entry.unique_id), mock_setup.entry.entry_id
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    rf_entity = next(e for e in entries if e.domain == Platform.RADIO_FREQUENCY)
    return mock_setup.api, rf_entity.entity_id


@pytest.mark.parametrize(
    ("device_name", "has_rf"),
    [
        ("Office", True),  # RMPRO
        ("Garage", True),  # RM4PRO
        ("Entrance", False),  # RMMINI
    ],
)
async def test_radio_frequency_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    device_name: str,
    has_rf: bool,
) -> None:
    """RF entity is created only for RF-capable devices."""
    device = get_device(device_name)
    mock_setup = await device.setup_entry(hass)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_setup.entry.unique_id), mock_setup.entry.entry_id
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    rf_entities = [e for e in entries if e.domain == Platform.RADIO_FREQUENCY]
    assert len(rf_entities) == (1 if has_rf else 0)


@pytest.mark.parametrize(
    ("timings", "repeat_count", "expected"),
    [
        pytest.param(
            [round(12 * _TICK_US), round(300 * _TICK_US), round(12 * _TICK_US)],
            3,
            bytes([0xB2, 0x03, 0x05, 0x00, 0x0C, 0x00, 0x01, 0x2C, 0x0C]),
            id="inline_and_escaped",
        ),
        pytest.param(
            [400, -10, 400],
            0,
            bytes([0xB2, 0x00, 0x03, 0x00, 0x0D, 0x01, 0x0D]),
            id="under_half_a_tick",
        ),
        pytest.param(
            [round(0xFFFF * _TICK_US)],
            0,
            bytes([0xB2, 0x00, 0x03, 0x00, 0x00, 0xFF, 0xFF]),
            id="max_ticks",
        ),
    ],
)
def test_encode_rf_packet(
    timings: list[int], repeat_count: int, expected: bytes
) -> None:
    """Pulses are encoded inline below 256 ticks, escape-prefixed above."""
    packet = encode_rf_packet(
        type_byte=_RF_433_TYPE_BYTE, repeat_count=repeat_count, timings_us=timings
    )
    assert packet == expected


async def test_send_command_rejects_too_long_timing(hass: HomeAssistant) -> None:
    """A timing too long to encode is rejected before send."""
    api, entity_id = await _setup_rf_device(hass)

    command = OOKCommand(frequency=_FREQ_433, timings=[400, -3_000_000])
    with pytest.raises(HomeAssistantError) as exc_info:
        await radio_frequency.async_send_command(hass, entity_id, command)
    assert exc_info.value.translation_key == "timing_too_long"
    api.send_data.assert_not_called()


async def test_send_command(hass: HomeAssistant) -> None:
    """An OOK command transmits the encoded packet once."""
    api, entity_id = await _setup_rf_device(hass)

    timings = [400, -800, 400, -800]
    command = OOKCommand(frequency=_FREQ_433, timings=timings)
    await radio_frequency.async_send_command(hass, entity_id, command)

    expected = encode_rf_packet(
        type_byte=_RF_433_TYPE_BYTE, repeat_count=0, timings_us=timings
    )
    assert api.send_data.call_args == call(expected)


async def test_send_command_315_band(hass: HomeAssistant) -> None:
    """A 315 MHz command uses the 0xB4 type byte."""
    api, entity_id = await _setup_rf_device(hass)

    command = OOKCommand(frequency=_FREQ_315, timings=[400, -800])
    await radio_frequency.async_send_command(hass, entity_id, command)

    assert api.send_data.call_args.args[0][0] == _RF_315_TYPE_BYTE


@pytest.mark.parametrize(
    ("frequency", "timings", "repeat_count", "expected"),
    [
        pytest.param(
            _FREQ_433,
            [400, -800, 400, -800],
            0,
            "b1c00800009f06000d1a0d1a",
            id="433_92",
        ),
        pytest.param(433_420_000, [400, -800], 0, "b1c006000c9d06000d1a", id="433_42"),
        pytest.param(_FREQ_315, [400, -800], 0, "b1c0060078ce04000d1a", id="315"),
        pytest.param(
            _FREQ_433,
            [400, -800, 400, -5000],
            3,
            "b1c01400009f06000d1a0da40d1a0da40d1a0da40d1a0da4",
            id="repeat_count_keeps_own_gap",
        ),
        pytest.param(
            _FREQ_433,
            [400, -800, 400],
            1,
            "b1c01000009f06000d1a0d0001a70d1a0d0001a7",
            id="ends_on_pulse",
        ),
    ],
)
async def test_send_command_rm4_pro(
    hass: HomeAssistant,
    frequency: int,
    timings: list[int],
    repeat_count: int,
    expected: str,
) -> None:
    """An RM4 Pro packet carries the frequency and writes out each repeat as a frame."""
    api, entity_id = await _setup_rf_device(hass, "Garage")

    command = OOKCommand(
        frequency=frequency, timings=timings, repeat_count=repeat_count
    )
    await radio_frequency.async_send_command(hass, entity_id, command)

    assert api.send_data.call_args == call(bytes.fromhex(expected))


@pytest.mark.parametrize(
    ("frequency", "expected"),
    [
        pytest.param(305_000_000, "b1c0060068a704000d1a", id="305"),
        pytest.param(433_000_000, "b1c00600689b06000d1a", id="433_00"),
        pytest.param(438_000_000, "b1c00600f0ae06000d1a", id="438"),
    ],
)
async def test_send_command_rm4_pro_measured_range(
    hass: HomeAssistant, frequency: int, expected: str
) -> None:
    """An RM4 Pro sends anywhere in its measured range."""
    api, entity_id = await _setup_rf_device(hass, "Garage")

    command = OOKCommand(frequency=frequency, timings=[400, -800])
    await radio_frequency.async_send_command(hass, entity_id, command)

    assert api.send_data.call_args == call(bytes.fromhex(expected))


@pytest.mark.parametrize(
    ("device_name", "frequency"),
    [
        pytest.param("Garage", 340_000_000, id="rm4_pro_340"),
        pytest.param("Garage", 440_000_000, id="rm4_pro_440"),
        pytest.param("Office", 433_000_000, id="rm_pro_433_00"),
    ],
)
async def test_send_command_rejects_outside_model_range(
    hass: HomeAssistant, device_name: str, frequency: int
) -> None:
    """A frequency outside the model's ranges is rejected before send."""
    api, entity_id = await _setup_rf_device(hass, device_name)

    command = OOKCommand(frequency=frequency, timings=[400, -800])
    with pytest.raises(HomeAssistantError):
        await radio_frequency.async_send_command(hass, entity_id, command)
    api.send_data.assert_not_called()


async def test_send_command_rm4_pro_rejects_invalid_timings(
    hass: HomeAssistant,
) -> None:
    """Timings that do not start with a pulse are rejected before send."""
    api, entity_id = await _setup_rf_device(hass, "Garage")

    command = OOKCommand(frequency=_FREQ_433, timings=[-400, 800])
    with pytest.raises(HomeAssistantError) as exc_info:
        await radio_frequency.async_send_command(hass, entity_id, command)
    assert exc_info.value.translation_key == "invalid_rf_timings"
    api.send_data.assert_not_called()


async def test_send_command_rejects_out_of_band(hass: HomeAssistant) -> None:
    """An out-of-band frequency is rejected before send."""
    api, entity_id = await _setup_rf_device(hass)

    command = OOKCommand(frequency=868_000_000, timings=[400, -800])
    with pytest.raises(HomeAssistantError):
        await radio_frequency.async_send_command(hass, entity_id, command)
    api.send_data.assert_not_called()


async def test_send_command_transmit_failure(hass: HomeAssistant) -> None:
    """A broadlink exception surfaces as HomeAssistantError."""
    api, entity_id = await _setup_rf_device(hass)
    api.send_data.side_effect = BroadlinkException("nope")

    command = OOKCommand(frequency=_FREQ_433, timings=[400, -800])
    with pytest.raises(HomeAssistantError):
        await radio_frequency.async_send_command(hass, entity_id, command)


async def test_entity_availability(hass: HomeAssistant) -> None:
    """Entity becomes unavailable when the device stops responding."""
    api, entity_id = await _setup_rf_device(hass)
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    api.check_sensors.side_effect = OSError("disconnected")
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=2))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
