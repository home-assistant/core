"""Sensor platform for the Fuelprices.dk integration."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    EntityCategory,
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify as util_slugify

from .const import DOMAIN
from .coordinator import APIClient

if TYPE_CHECKING:
    from . import FuelpricesDkConfigEntry

SENSORS = [
    SensorEntityDescription(
        key="price",
        name="Fuel Price",
        native_unit_of_measurement="DKK/L",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gas-station",
    ),
    SensorEntityDescription(
        key="last_updated",
        name="Last Updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FuelpricesDkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform for Fuelprices.dk."""

    for coordinator in entry.runtime_data.values():
        subentry_sensors = []
        for sensor in SENSORS:
            if sensor.key == "last_updated":
                subentry_sensors.append(
                    FuelpricesDkSensor(
                        coordinator,
                        coordinator.station_name,
                        "last_updated",
                        "Last Updated",
                        sensor,
                    )
                )
                continue

            for product_key, product_info in coordinator.products.items():
                product_name = product_info["name"]
                subentry_sensors.append(
                    FuelpricesDkSensor(
                        coordinator,
                        coordinator.station_name,
                        product_key,
                        product_name if isinstance(product_name, str) else product_key,
                        sensor,
                    )
                )

        async_add_entities(subentry_sensors, config_subentry_id=coordinator.subentry_id)


class FuelpricesDkSensor(CoordinatorEntity[APIClient], RestoreSensor):
    """Sensor for Fuelprices.dk."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: APIClient,
        station_name: str,
        product_key: str,
        product_name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._product_key = product_key
        self._product_name = product_name
        self._station_name = station_name

        self._attr_name = self._product_name

        self._attr_unique_id = util_slugify(
            f"{self.coordinator.station_id}_{self.entity_description.key}_{product_key}"
        )
        self._attr_config_subentry_id = self.coordinator.subentry_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self.coordinator.station_id))},
            entry_type=DeviceEntryType.SERVICE,
            name=self._station_name,
            manufacturer=self.coordinator.company,
            model=self.coordinator.station_name,
        )

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        if self.entity_description.key == "last_updated":
            return super().available

        return super().available and self._product_key in self.coordinator.products

    @property
    def native_value(self) -> datetime | float | None:
        """Return the current value of the sensor."""
        if self.entity_description.key == "last_updated":
            return self.coordinator.updated_at

        if (product := self.coordinator.products.get(self._product_key)) is None:
            return None

        if isinstance(price := product.get("price"), int | float):
            return float(price)

        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
