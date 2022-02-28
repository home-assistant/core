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
        LaundrifyPowerPlug(coordinator, idx) for idx, ent in enumerate(coordinator.data)
    )


class LaundrifyPowerPlug(CoordinatorEntity, BinarySensorEntity):
    """Representation of a laundrify Power Plug."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:washing-machine"

    def __init__(self, coordinator, idx):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.idx = idx
        self._attr_unique_id = coordinator.data[idx]["_id"]
        self._attr_name = coordinator.data[idx]["name"]

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
            "sw_version": self.coordinator.data[self.idx]["firmwareVersion"],
        }

    @property
    def is_on(self):
        """Return entity state."""
        try:
            return self.coordinator.data[self.idx]["status"] == "ON"
        except IndexError:
            _LOGGER.warning("The backend didn't return any data for this device")
            self._attr_available = False
            return None
