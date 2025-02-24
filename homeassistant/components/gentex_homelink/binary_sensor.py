"""Platform for BinarySensor integration."""

from __future__ import annotations

from datetime import timedelta
import time

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

# Import the device class from the component that you want to support
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the entities for the binary sensor."""
    coordinator = config_entry.runtime_data.coordinator
    async_add_entities(coordinator.buttons)


class HomeLinkBinarySensor(
    CoordinatorEntity["HomeLinkCoordinator"], BinarySensorEntity
):
    """Binary sensor."""

    def __init__(self, id, name, device_info, coordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator, context=id)
        self.id = id
        self._attr_has_entity_name = True
        self.name = name
        self.unique_id = f"{DOMAIN}.{id}"
        self.device_info = device_info
        self.on = False
        self.last_request_id = None

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.on

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update this button."""
        if not self.coordinator.data or self.id not in self.coordinator.data:
            self.on = False
        else:
            latest_update = self.coordinator.data[self.id]
            self.on = (time.time() - latest_update["timestamp"]) < 10 and latest_update[
                "requestId"
            ] != self.last_request_id
            self.last_request_id = latest_update["requestId"]
        self.async_write_ha_state()
