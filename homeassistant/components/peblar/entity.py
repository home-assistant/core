"""Base entity for the Peblar integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PeblarConfigEntry, PeblarMeterDataUpdateCoordinator


class PeblarEntity(CoordinatorEntity[PeblarMeterDataUpdateCoordinator], Entity):
    """Defines a Peblar entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: PeblarConfigEntry) -> None:
        """Initialize the Peblar entity."""
        super().__init__(coordinator=entry.runtime_data)
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{entry.data[CONF_HOST]}",
            identifiers={(DOMAIN, str(entry.unique_id))},
            manufacturer="Peblar",
            name="Peblar EV charger",
        )
