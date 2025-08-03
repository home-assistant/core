"""Green Planet Energy sensor platform."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import SENSOR_HOURS
from .coordinator import GreenPlanetEnergyUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class GreenPlanetEnergySensorEntityDescription(SensorEntityDescription):
    """Describes Green Planet Energy sensor entity."""

    hour: int


SENSOR_DESCRIPTIONS: list[GreenPlanetEnergySensorEntityDescription] = [
    GreenPlanetEnergySensorEntityDescription(
        key=f"gpe_price_{hour:02d}",
        translation_key=f"price_{hour:02d}",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=4,
        hour=hour,
    )
    for hour in SENSOR_HOURS
] + [
    # Additional sensors for statistics
    GreenPlanetEnergySensorEntityDescription(
        key="gpe_highest_price_today",
        translation_key="highest_price_today",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=4,
        hour=-1,  # Special value to indicate this is not an hourly sensor
    ),
    GreenPlanetEnergySensorEntityDescription(
        key="gpe_lowest_price_today",
        translation_key="lowest_price_today",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=4,
        hour=-1,  # Special value to indicate this is not an hourly sensor
    ),
    GreenPlanetEnergySensorEntityDescription(
        key="gpe_current_price",
        translation_key="current_price",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=4,
        hour=-1,  # Special value to indicate this is not an hourly sensor
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Green Planet Energy sensors."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        GreenPlanetEnergySensor(coordinator, description, config_entry)
        for description in SENSOR_DESCRIPTIONS
    )


class GreenPlanetEnergySensor(
    CoordinatorEntity[GreenPlanetEnergyUpdateCoordinator], SensorEntity
):
    """Representation of a Green Planet Energy sensor."""

    entity_description: GreenPlanetEnergySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GreenPlanetEnergyUpdateCoordinator,
        description: GreenPlanetEnergySensorEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = description.key

        # Set appropriate name based on sensor type
        if description.hour >= 0:
            self._attr_name = f"Preis {description.hour:02d}:00"
        else:
            # For special sensors, the name will be set via translation_key
            self._attr_name = None

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        # Handle different sensor types
        if self.entity_description.key == "gpe_highest_price_today":
            return self._get_highest_price_today()
        if self.entity_description.key == "gpe_lowest_price_today":
            return self._get_lowest_price_today()
        if self.entity_description.key == "gpe_current_price":
            return self._get_current_price()
        # Regular hourly sensor
        return self.coordinator.data.get(self.entity_description.key)

    def _get_highest_price_today(self) -> float | None:
        """Get the highest price from today's data."""
        if not self.coordinator.data:
            return None

        prices = []
        for hour in range(24):
            price_key = f"gpe_price_{hour:02d}"
            if price_key in self.coordinator.data:
                price = self.coordinator.data[price_key]
                if price is not None:
                    prices.append(price)

        return max(prices) if prices else None

    def _get_lowest_price_today(self) -> float | None:
        """Get the lowest price from today's data."""
        if not self.coordinator.data:
            return None

        prices = []
        for hour in range(24):
            price_key = f"gpe_price_{hour:02d}"
            if price_key in self.coordinator.data:
                price = self.coordinator.data[price_key]
                if price is not None:
                    prices.append(price)

        return min(prices) if prices else None

    def _get_current_price(self) -> float | None:
        """Get the price for the current hour."""
        if not self.coordinator.data:
            return None

        current_hour = dt_util.now().hour
        price_key = f"gpe_price_{current_hour:02d}"
        return self.coordinator.data.get(price_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if self.entity_description.hour >= 0:
            # Regular hourly sensor
            return {
                "hour": self.entity_description.hour,
                "time_slot": f"{self.entity_description.hour:02d}:00-{self.entity_description.hour + 1:02d}:00",
            }
        if self.entity_description.key == "gpe_highest_price_today":
            # Find the hour with the highest price
            highest_price = self._get_highest_price_today()
            highest_hour = None
            if highest_price is not None and self.coordinator.data:
                for hour in range(24):
                    price_key = f"gpe_price_{hour:02d}"
                    if self.coordinator.data.get(price_key) == highest_price:
                        highest_hour = hour
                        break
            return {
                "highest_price_hour": highest_hour,
                "time_slot": f"{highest_hour:02d}:00-{highest_hour + 1:02d}:00"
                if highest_hour is not None
                else None,
            }
        if self.entity_description.key == "gpe_lowest_price_today":
            # Find the hour with the lowest price
            lowest_price = self._get_lowest_price_today()
            lowest_hour = None
            if lowest_price is not None and self.coordinator.data:
                for hour in range(24):
                    price_key = f"gpe_price_{hour:02d}"
                    if self.coordinator.data.get(price_key) == lowest_price:
                        lowest_hour = hour
                        break
            return {
                "lowest_price_hour": lowest_hour,
                "time_slot": f"{lowest_hour:02d}:00-{lowest_hour + 1:02d}:00"
                if lowest_hour is not None
                else None,
            }
        if self.entity_description.key == "gpe_current_price":
            current_hour = dt_util.now().hour
            return {
                "current_hour": current_hour,
                "time_slot": f"{current_hour:02d}:00-{current_hour + 1:02d}:00",
            }

        return None
