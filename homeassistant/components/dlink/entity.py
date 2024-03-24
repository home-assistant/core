"""Entity representing a D-Link Power Plug device."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CONNECTIONS
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER
from .data import SmartPlugData


class DLinkEntity(Entity):
    """Representation of a D-Link Power Plug entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: ConfigEntry,
        data: SmartPlugData,
        description: EntityDescription,
    ) -> None:
        """Initialize a D-Link Power Plug entity."""
        self.data = data
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=data.smartplug.model_name,
            name=config_entry.title,
        )
        if config_entry.unique_id:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (dr.CONNECTION_NETWORK_MAC, config_entry.unique_id)
            }
