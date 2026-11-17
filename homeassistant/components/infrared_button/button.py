"""Button platform for the Infrared button integration."""

from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.components.infrared import (
    InfraredCommand,
    InfraredEmitterConsumerEntity,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_INFRARED_ENTITY_ID, CONF_MODULATION, CONF_TIMINGS, DOMAIN

PARALLEL_UPDATES = 1


class LearnedInfraredCommand(InfraredCommand):
    """IR command that replays raw timings captured from a remote."""

    def __init__(self, timings: list[int], modulation: int) -> None:
        """Initialize the command."""
        super().__init__(modulation=modulation)
        self._timings = timings

    @override
    def get_raw_timings(self) -> list[int]:
        """Return the captured timings."""
        return self._timings


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a button for each learned command."""
    for subentry_id, subentry in entry.subentries.items():
        async_add_entities(
            [InfraredButtonEntity(entry, subentry)], config_subentry_id=subentry_id
        )


class InfraredButtonEntity(InfraredEmitterConsumerEntity, ButtonEntity):
    """Button that sends a learned IR command."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        self._attr_name = subentry.title
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})
        self._infrared_emitter_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
        self._command = LearnedInfraredCommand(
            subentry.data[CONF_TIMINGS], subentry.data[CONF_MODULATION]
        )

    @override
    async def async_press(self) -> None:
        """Send the learned command."""
        await self._send_command(self._command)
