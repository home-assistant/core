"""Sensor platform for the Fuelprices.dk integration."""

from typing import TYPE_CHECKING, override

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify as util_slugify

from .const import DOMAIN
from .coordinator import FuelPricesDKCoordinator

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
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FuelpricesDkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform for Fuelprices.dk."""

    for coordinator in entry.runtime_data.values():
        async_add_entities(
            (
                FuelpricesDkSensor(
                    coordinator,
                    coordinator.station_name,
                    product_key,
                    sensor,
                )
                for sensor in SENSORS
                for product_key in coordinator.data
            ),
            config_subentry_id=coordinator.subentry_id,
        )


class FuelpricesDkSensor(CoordinatorEntity[FuelPricesDKCoordinator], RestoreSensor):
    """Sensor for Fuelprices.dk."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FuelPricesDKCoordinator,
        station_name: str,
        product_key: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._product_key = product_key
        self._station_name = station_name

        self._attr_name = product_key

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
    @override
    def available(self) -> bool:
        """Return whether the entity is available."""
        return super().available and self._product_key in self.coordinator.data

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value of the sensor."""
        price = self.coordinator.data[self._product_key]
        if isinstance(price, int | float):
            return float(price)
        return None
