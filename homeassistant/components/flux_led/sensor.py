"""Support for Magic Home sensors."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FluxLedConfigEntry
from .entity import FluxEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FluxLedConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Magic Home sensors."""
    coordinator = entry.runtime_data
    if coordinator.device.paired_remotes is not None:
        async_add_entities(
            [
                FluxPairedRemotes(
                    coordinator,
                    entry.unique_id or entry.entry_id,
                    "paired_remotes",
                )
            ]
        )


class FluxPairedRemotes(FluxEntity, SensorEntity):
    """Representation of a Magic Home paired remotes sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "paired_remotes"

    @property
    def native_value(self) -> int:
        """Return the number of paired remotes."""
        assert self._device.paired_remotes is not None
        return self._device.paired_remotes
