"""Radio Frequency platform for Broadlink."""

from __future__ import annotations

import logging

from broadlink.exceptions import BroadlinkException
from rf_protocols import RadioFrequencyCommand

from homeassistant.components.radio_frequency import RadioFrequencyTransmitterEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .device import BroadlinkDevice
from .entity import BroadlinkEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

_TICK_US = 32.84

_RF_433_TYPE_BYTE = 0xB2
_RF_315_TYPE_BYTE = 0xB4

_RF_433_RANGE = (433_050_000, 434_790_000)
_RF_315_RANGE = (314_950_000, 315_250_000)

SUPPORTED_FREQUENCY_RANGES: list[tuple[int, int]] = [_RF_433_RANGE, _RF_315_RANGE]


def _type_byte_for_frequency(frequency: int) -> int:
    """Return the Broadlink RF type byte for a given carrier frequency."""
    if _RF_433_RANGE[0] <= frequency <= _RF_433_RANGE[1]:
        return _RF_433_TYPE_BYTE
    if _RF_315_RANGE[0] <= frequency <= _RF_315_RANGE[1]:
        return _RF_315_TYPE_BYTE
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="frequency_not_supported",
        translation_placeholders={"frequency": f"{frequency / 1_000_000:g}"},
    )


def encode_rf_packet(
    *,
    type_byte: int,
    repeat_count: int,
    timings_us: list[int],
) -> bytes:
    """Encode raw OOK timings as a Broadlink RF pulse-length packet.

    The layout is::

        byte 0           type byte (0xB2 for 433 MHz, 0xB4 for 315 MHz)
        byte 1           repeat count (additional transmissions after the first)
        bytes 2..3       payload length (little-endian), counted from byte 4
        bytes 4..N-1     pulses: 1 byte when ticks < 256, otherwise
                         0x00 followed by a 2-byte big-endian tick count

    Each pulse is expressed as multiples of 32.84 µs ticks, which is the
    timing resolution of the Broadlink RF front-end.
    """
    buf = bytearray([type_byte, repeat_count, 0, 0])
    for duration in timings_us:
        ticks = round(abs(duration) / _TICK_US)
        div, mod = divmod(ticks, 256)
        if div:
            buf.append(0x00)
            buf.append(div)
        buf.append(mod)
    payload_len = len(buf) - 4
    buf[2] = payload_len & 0xFF
    buf[3] = (payload_len >> 8) & 0xFF
    return bytes(buf)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Broadlink radio frequency transmitter."""
    # Uses legacy hass.data[DOMAIN] pattern
    # pylint: disable-next=hass-use-runtime-data
    device: BroadlinkDevice = hass.data[DOMAIN].devices[config_entry.entry_id]
    async_add_entities([BroadlinkRadioFrequency(device)])


class BroadlinkRadioFrequency(BroadlinkEntity, RadioFrequencyTransmitterEntity):
    """Representation of a Broadlink RF transmitter."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, device: BroadlinkDevice) -> None:
        """Initialize the entity."""
        super().__init__(device)
        self._attr_unique_id = device.unique_id

    @property
    def supported_frequency_ranges(self) -> list[tuple[int, int]]:
        """Return the Broadlink-supported narrow RF bands."""
        return SUPPORTED_FREQUENCY_RANGES

    async def async_send_command(self, command: RadioFrequencyCommand) -> None:
        """Encode an OOK command and transmit it via the Broadlink device."""
        type_byte = _type_byte_for_frequency(command.frequency)
        packet = encode_rf_packet(
            type_byte=type_byte,
            repeat_count=command.repeat_count,
            timings_us=command.get_raw_timings(),
        )
        _LOGGER.debug(
            "Transmitting RF packet: %d bytes on %d Hz (repeat=%d)",
            len(packet),
            command.frequency,
            command.repeat_count,
        )

        device = self._device
        try:
            await device.async_request(device.api.send_data, packet)
        except (BroadlinkException, OSError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="transmit_failed",
                translation_placeholders={"error": str(err)},
            ) from err
