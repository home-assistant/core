"""Amber Electric Binary Sensor definitions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import AmberUpdateCoordinator

PRICE_SPIKE_ICONS = {
    "none": "mdi:power-plug",
    "potential": "mdi:power-plug-outline",
    "spike": "mdi:power-plug-off",
}


class AmberPriceGridSensor(CoordinatorEntity, BinarySensorEntity):
    """Sensor to show single grid binary values."""

    def __init__(
        self,
        coordinator: AmberUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the Sensor."""
        super().__init__(coordinator)
        self.site_id = coordinator.site_id
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.site_id}-{description.key}"
        self._attr_device_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.coordinator.data["grid"][self.entity_description.key]


class AmberPriceSpikeBinarySensor(AmberPriceGridSensor):
    """Sensor to show single grid binary values."""

    @property
    def icon(self):
        """Return the sensor icon."""
        status = self.coordinator.data["grid"]["price_spike"]
        return PRICE_SPIKE_ICONS[status]

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.coordinator.data["grid"]["price_spike"] == "spike"

    @property
    def device_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional pieces of information about the price spike."""

        spike_status = self.coordinator.data["grid"]["price_spike"]
        return {
            "spike_status": spike_status,
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a config entry."""
    coordinator: AmberUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list = []
    price_spike_description = BinarySensorEntityDescription(
        key="price_spike",
        name=f"{entry.title} - Price Spike",
    )
    entities.append(AmberPriceSpikeBinarySensor(coordinator, price_spike_description))
    async_add_entities(entities)
