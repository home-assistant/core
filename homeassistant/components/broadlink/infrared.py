"""Infrared platform for Broadlink remotes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from broadlink.exceptions import BroadlinkException
from broadlink.remote import pulses_to_data as _bl_pulses_to_data

from homeassistant.components.infrared import InfraredCommand, InfraredEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import BroadlinkEntity

if TYPE_CHECKING:
    from .device import BroadlinkDevice

PARALLEL_UPDATES = 1


def _timings_to_broadlink_packet(timings: list[int]) -> bytes:
    """Convert signed microsecond timings to a Broadlink IR packet.

    Positive values are pulse (high) durations; negative values are space
    (low) durations. The Broadlink library's encoder expects absolute
    durations.
    """
    pulses = [abs(t) for t in timings]
    return _bl_pulses_to_data(pulses)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Broadlink infrared entity."""
    # Uses legacy hass.data[DOMAIN] pattern
    # pylint: disable-next=hass-use-runtime-data
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    async_add_entities([BroadlinkInfraredEntity(device)])


class BroadlinkInfraredEntity(BroadlinkEntity, InfraredEntity):
    """Broadlink infrared transmitter entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "infrared_emitter"

    def __init__(self, device: BroadlinkDevice) -> None:
        """Initialize the entity."""
        super().__init__(device)
        self._attr_unique_id = f"{device.unique_id}-emitter"

    async def async_send_command(self, command: InfraredCommand) -> None:
        """Send an IR command via the Broadlink device."""
        packet = _timings_to_broadlink_packet(command.get_raw_timings())
        try:
            await self._device.async_request(self._device.api.send_data, packet)
        except (BroadlinkException, OSError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
