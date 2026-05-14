"""Envertech EVT800 entity."""

from __future__ import annotations

import pyenvertechevt800

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EnvertechEVT800Coordinator


class EnvertechEVT800Entity(CoordinatorEntity[EnvertechEVT800Coordinator]):
    """Envertech EVT800 entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        evt800: pyenvertechevt800.EnvertechEVT800,
        coordinator: EnvertechEVT800Coordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize Envertech EVT800 entity."""
        super().__init__(coordinator)
        self.evt800 = evt800
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            configuration_url=f"http://{entry.data[CONF_IP_ADDRESS]}/",
            manufacturer="Envertech",
            model_id="EVT800",
            name="Envertech EVT800",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.evt800.online
