"""Platform for binary sensor integration."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors from a config entry created in the integrations UI."""

    coordinator = hass.data[DOMAIN][config.entry_id]["coordinator"]

    async_add_entities(
        LaundrifyPowerPlug(coordinator, device) for device in coordinator.data.values()
    )


class LaundrifyPowerPlug(CoordinatorEntity, BinarySensorEntity):
    """Representation of a laundrify Power Plug."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:washing-machine"

    def __init__(self, coordinator, device):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._attr_unique_id = device["_id"]
        self._attr_name = device["name"]

    @property
    def device_info(self):
        """Configure the Device of this Entity."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": self.coordinator.data[self.unique_id]["firmwareVersion"],
        }

    @property
    def available(self) -> bool:
        """Check if the device is available."""
        return self.unique_id in self.coordinator.data

    @property
    def is_on(self):
        """Return entity state."""
        if self.available:
            return self.coordinator.data[self.unique_id]["status"] == "ON"

        return None
