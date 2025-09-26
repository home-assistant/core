"""Amber Electric Binary Sensor definitions."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION
from .coordinator import AmberConfigEntry, AmberUpdateCoordinator

PRICE_SPIKE_ICONS = {
    "none": "mdi:power-plug",
    "potential": "mdi:power-plug-outline",
    "spike": "mdi:power-plug-off",
}


class AmberPriceGridSensor(
    CoordinatorEntity[AmberUpdateCoordinator], BinarySensorEntity
):
    """Sensor to show single grid binary values."""

    _attr_attribution = ATTRIBUTION

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

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.coordinator.data["grid"][self.entity_description.key]  # type: ignore[no-any-return]


class AmberPriceSpikeBinarySensor(AmberPriceGridSensor):
    """Sensor to show single grid binary values."""

    @property
    def icon(self) -> str:
        """Return the sensor icon."""
        status = self.coordinator.data["grid"]["price_spike"]
        return PRICE_SPIKE_ICONS[status]

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.coordinator.data["grid"]["price_spike"] == "spike"  # type: ignore[no-any-return]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional pieces of information about the price spike."""

        spike_status = self.coordinator.data["grid"]["price_spike"]
        return {
            "spike_status": spike_status,
        }


class AmberDemandWindowBinarySensor(AmberPriceGridSensor):
    """Sensor to show whether demand window is active."""

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        grid = self.coordinator.data["grid"]
        if "demand_window" in grid:
            return grid["demand_window"]  # type: ignore[no-any-return]
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmberConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a config entry."""
    coordinator = entry.runtime_data

    price_spike_description = BinarySensorEntityDescription(
        key="price_spike",
        name=f"{entry.title} - Price Spike",
    )
    demand_window_description = BinarySensorEntityDescription(
        key="demand_window",
        name=f"{entry.title} - Demand Window",
        translation_key="demand_window",
    )
    async_add_entities(
        [
            AmberPriceSpikeBinarySensor(coordinator, price_spike_description),
            AmberDemandWindowBinarySensor(coordinator, demand_window_description),
        ]
    )
