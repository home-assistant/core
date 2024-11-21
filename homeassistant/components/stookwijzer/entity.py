"""The Stookwijzer integration entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class StookwijzerEntity(CoordinatorEntity, Entity):
    """Base class for Stookwijzer entities."""

    _attr_attribution = "Data provided by atlasleefomgeving.nl"
    _attr_has_entity_name = True

    def __init__(
        self,
        description: EntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize a Stookwijzer device."""

        self.entity_description = description
        self._coordinator = entry.runtime_data

        super().__init__(self._coordinator)

        self._attr_unique_id = f"{entry.entry_id}{DOMAIN}{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Atlas Leefomgeving",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://www.atlasleefomgeving.nl/stookwijzer",
        )
