"""Infrared platform for Broadlink remotes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from broadlink.exceptions import BroadlinkException
from broadlink.remote import pulses_to_data as _bl_pulses_to_data
import infrared_protocols

from homeassistant.components.infrared import InfraredCommand, InfraredEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, IR_PACKET_REPEAT_INDEX
from .entity import BroadlinkEntity

if TYPE_CHECKING:
    from .device import BroadlinkDevice

PARALLEL_UPDATES = 1


class BroadlinkIRCommand(InfraredCommand):
    """Raw IR command with optional Broadlink hardware repeat count.

    This class lets you send raw timing data through a Broadlink infrared
    entity. The repeat_count maps directly to the Broadlink packet repeat
    byte: the device will re-transmit the entire IR burst that many
    additional times after the first transmission.

    Use this when you have existing Broadlink-encoded IR data (e.g. from
    IR code databases like SmartIR) and want to use it with the new
    infrared platform.

    Protocol-aware commands (infrared_protocols.NECCommand, LgTVCommand,
    etc.) manage repeats *inside* get_raw_timings() and should use the
    default repeat=0. Only BroadlinkIRCommand should set hardware repeat.

    Example: Migrating IR code database base64 codes to the infrared platform:

        import base64
        from broadlink.remote import data_to_pulses
        from homeassistant.components.broadlink.infrared import BroadlinkIRCommand
        from homeassistant.components.broadlink.const import IR_PACKET_REPEAT_INDEX

        # Decode base64 IR code (e.g. from IR code database)
        packet_data = base64.b64decode(b64_code)
        repeat_count = packet_data[IR_PACKET_REPEAT_INDEX]

        # Parse Broadlink packet to microsecond timings
        pulses = data_to_pulses(packet_data)
        timings = list(zip(pulses[::2], pulses[1::2]))
        if len(pulses) % 2:
            timings.append((pulses[-1], 0))

        # Create command
        cmd = BroadlinkIRCommand(timings, repeat_count=repeat_count)
        await infrared.async_send_command(hass, entity_id, cmd)
    """

    # Standard IR carrier frequency. Broadlink hardware handles the carrier
    # internally, so this value is informational only.
    MODULATION = 38000

    def __init__(
        self,
        timings: list[tuple[int, int]],
        repeat_count: int = 0,
    ) -> None:
        """Initialize with timing pairs and optional repeat count.

        Args:
            timings: List of (mark_us, space_us) pairs in microseconds.
            repeat_count: Broadlink hardware repeat count (0 = send once).
                Must be 0–255 (the hardware repeat byte is a single unsigned byte).

        Raises:
            ValueError: If repeat_count is outside 0–255 range.
        """
        if not 0 <= repeat_count <= 255:
            raise ValueError(f"repeat_count must be 0–255, got {repeat_count}")
        super().__init__(modulation=self.MODULATION, repeat_count=repeat_count)
        self._timings = [
            infrared_protocols.Timing(high_us=high, low_us=low) for high, low in timings
        ]

    def get_raw_timings(self) -> list[infrared_protocols.Timing]:
        """Return timing pairs for transmission."""
        return self._timings


def timings_to_broadlink_packet(
    timings: list[tuple[int, int]],
    repeat: int = 0,
) -> bytes:
    """Convert raw timing pairs (high_us, low_us) to a Broadlink IR packet.

    Args:
        timings: List of (mark_us, space_us) pairs in microseconds.
        repeat: Number of extra repeats (0 = send once).

    Returns:
        Binary packet ready for Broadlink send_data().

    """
    if not 0 <= repeat <= 255:
        raise ValueError(f"repeat must be 0–255, got {repeat}")

    # Flatten (mark, space) pairs into a pulse list, omitting any zero-length spaces
    pulses: list[int] = []
    for high_us, low_us in timings:
        pulses.append(high_us)
        if low_us:
            pulses.append(low_us)

    # Use broadlink library's encoder (tick=32.84 µs)
    packet = bytearray(_bl_pulses_to_data(pulses))
    packet[IR_PACKET_REPEAT_INDEX] = repeat
    return bytes(packet)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Broadlink infrared entity."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    async_add_entities([BroadlinkInfraredEntity(device)])


class BroadlinkInfraredEntity(BroadlinkEntity, InfraredEntity):
    """Broadlink infrared transmitter entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "infrared"

    def __init__(self, device: BroadlinkDevice) -> None:
        """Initialize the entity."""
        super().__init__(device)
        self._attr_unique_id = f"{device.unique_id}-infrared"

    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command via the Broadlink device.

        Handles two types of repeat behavior:

        1. Protocol-aware commands (NECCommand, etc.): These encode repeats
           (like NEC repeat codes) inside their get_raw_timings() data. The
           Broadlink packet is sent with repeat=0.

        2. BroadlinkIRCommand: Carries Broadlink hardware repeat count,
           which tells the device to re-transmit the entire burst N times.
           This is used for protocols/commands that need multiple full frame
           transmissions (e.g. legacy SmartIR data).

        Using isinstance check ensures protocol-level repeats (already in
        timing data) don't get conflated with hardware repeats.
        """
        timings = [
            (timing.high_us, timing.low_us) for timing in command.get_raw_timings()
        ]

        # Only BroadlinkIRCommand uses Broadlink hardware repeat. Protocol-aware
        # commands (NECCommand, etc.) encode repeats inside get_raw_timings()
        # and must use hardware repeat=0 to avoid double-repeating.
        if isinstance(command, BroadlinkIRCommand):
            repeat = command.repeat_count
        else:
            repeat = 0

        packet = timings_to_broadlink_packet(timings, repeat=repeat)

        try:
            await self._device.async_request(self._device.api.send_data, packet)
        except (BroadlinkException, OSError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
