"""Envertech EVT800 entity."""

from __future__ import annotations

import pyenvertechevt800

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EnvertechEVT800Coordinator


class EnvertechEVT800Entity(CoordinatorEntity[EnvertechEVT800Coordinator]):
    """Envertech EVT800 entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        evt800: pyenvertechevt800.EnvertechEVT800,
        coordinator: EnvertechEVT800Coordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize Envertech EVT800 entity."""
        super().__init__(coordinator)
        self.evt800 = evt800
        self._attr_unique_id = (
            f"{DOMAIN}-{entry.data[CONF_IP_ADDRESS]}-{entry.data[CONF_PORT]}"
        )
        self._attr_entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{DOMAIN}-{entry.data[CONF_IP_ADDRESS]}-{entry.data[CONF_PORT]}",
                )
            },
            configuration_url=f"http://{entry.data[CONF_IP_ADDRESS]}/",
            manufacturer="Envertech",
            model="EVT800",
            name="Envertech EVT800",
            sw_version="1.0.0",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.evt800.online is True

    async def async_will_remove_from_hass(self) -> None:
        """Stop the evt800 device when coordinator is removed from hass."""
        if hasattr(self.evt800, "stop") and callable(self.evt800.stop):
            await self.evt800.stop()
