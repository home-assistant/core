"""Tests for the Broadlink radio_frequency platform."""

from __future__ import annotations

from datetime import timedelta
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
from homeassistant.util import dt as dt_util

from . import get_device

from tests.common import async_fire_time_changed

_FREQ_433 = 433_920_000
_FREQ_315 = 315_000_000


async def _setup_rf_device(hass: HomeAssistant) -> tuple[MagicMock, str]:
    """Set up the RMPRO test device, return its api mock and RF entity_id."""
    device = get_device("Office")
    mock_setup = await device.setup_entry(hass)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
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
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    rf_entities = [e for e in entries if e.domain == Platform.RADIO_FREQUENCY]
    assert len(rf_entities) == (1 if has_rf else 0)


def test_encode_rf_packet() -> None:
    """Pulses are encoded inline below 256 ticks, escape-prefixed above."""
    timings = [round(12 * _TICK_US), round(300 * _TICK_US), round(12 * _TICK_US)]
    packet = encode_rf_packet(
        type_byte=_RF_433_TYPE_BYTE, repeat_count=3, timings_us=timings
    )
    # type byte, repeat count, payload length (le16), 12, escape (00 01 2c), 12
    assert packet == bytes([0xB2, 0x03, 0x05, 0x00, 0x0C, 0x00, 0x01, 0x2C, 0x0C])


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
