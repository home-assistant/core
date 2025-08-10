"""Green Planet Energy sensor platform."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
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


SENSOR_HOURLY_DESCRIPTIONS: list[GreenPlanetEnergySensorEntityDescription] = [
    GreenPlanetEnergySensorEntityDescription(
        key=f"gpe_price_{hour:02d}",
        translation_key=f"price_{hour:02d}",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=4,
        hour=hour,
    )
    for hour in SENSOR_HOURS
]

SENSOR_STAT_DESCRIPTIONS: list[GreenPlanetEnergySensorEntityDescription] = [
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
        key="gpe_lowest_price_day",
        translation_key="lowest_price_day",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=4,
        hour=-2,  # Special value for day period (6-18h)
    ),
    GreenPlanetEnergySensorEntityDescription(
        key="gpe_lowest_price_night",
        translation_key="lowest_price_night",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=4,
        hour=-3,  # Special value for night period (18-6h)
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

SENSOR_DESCRIPTIONS: list[GreenPlanetEnergySensorEntityDescription] = (
    SENSOR_HOURLY_DESCRIPTIONS + SENSOR_STAT_DESCRIPTIONS
)


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
        # Use fixed unique_id with just the key for predictable entity IDs
        self._attr_unique_id = description.key

        # Set explicit entity_id to ensure gpe_ prefix for all sensors
        if description.hour >= 0:
            # For hourly sensors, use gpe_price_XX format
            self.entity_id = f"sensor.{description.key}"
        else:
            # For special sensors, use the full key
            self.entity_id = f"sensor.{description.key}"

        # Set appropriate name based on sensor type
        if description.hour >= 0:
            self._attr_name = f"Price {description.hour:02d}:00"
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
        if self.entity_description.key == "gpe_lowest_price_day":
            return self._get_lowest_price_day()
        if self.entity_description.key == "gpe_lowest_price_night":
            return self._get_lowest_price_night()
        if self.entity_description.key == "gpe_current_price":
            return self._get_current_price()
        if self.entity_description.key == "gpe_price_chart_24h":
            return self._get_current_price()  # Use current price as main value

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

    def _get_lowest_price_day(self) -> float | None:
        """Get the lowest price during day hours (6-18)."""
        if not self.coordinator.data:
            return None

        prices = []
        # Tag: 6-18 Uhr (6, 7, 8, ..., 17)
        for hour in range(6, 18):
            price_key = f"gpe_price_{hour:02d}"
            if price_key in self.coordinator.data:
                price = self.coordinator.data[price_key]
                if price is not None:
                    prices.append(price)

        return min(prices) if prices else None

    def _get_lowest_price_night(self) -> float | None:
        """Get the lowest price during night hours (18-6)."""
        if not self.coordinator.data:
            return None

        prices = []
        # Nacht: 18-24 Uhr und 0-6 Uhr
        # Abend: 18, 19, 20, 21, 22, 23
        for hour in range(18, 24):
            price_key = f"gpe_price_{hour:02d}"
            if price_key in self.coordinator.data:
                price = self.coordinator.data[price_key]
                if price is not None:
                    prices.append(price)

        # Frühe Morgenstunden: 0, 1, 2, 3, 4, 5
        for hour in range(6):
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

    def _get_24h_chart_data(self) -> list[dict[str, Any]]:
        """Get next 24 hours of price data for charting."""
        if not self.coordinator.data:
            return []

        chart_data = []
        current_hour = dt_util.now().hour

        # Get remaining hours of today (from current hour to 23)
        for hour in range(current_hour, 24):
            price_key = f"gpe_price_{hour:02d}"
            price = self.coordinator.data.get(price_key)

            # Create datetime for this hour
            hour_datetime = dt_util.now().replace(
                hour=hour, minute=0, second=0, microsecond=0
            )

            chart_data.append(
                {
                    "hour": hour,
                    "price": price,
                    "datetime": hour_datetime.isoformat(),
                    "time_slot": f"{hour:02d}:00-{hour + 1:02d}:00",
                    "day": "today",
                }
            )

        # Get tomorrow's hours to fill up to 24 hours total
        hours_needed = 24 - len(chart_data)
        for hour in range(hours_needed):
            price_key = f"gpe_price_{hour:02d}_tomorrow"
            price = self.coordinator.data.get(price_key)

            # Create datetime for tomorrow's hour
            tomorrow_datetime = (dt_util.now() + timedelta(days=1)).replace(
                hour=hour, minute=0, second=0, microsecond=0
            )

            chart_data.append(
                {
                    "hour": hour,
                    "price": price,
                    "datetime": tomorrow_datetime.isoformat(),
                    "time_slot": f"{hour:02d}:00-{hour + 1:02d}:00",
                    "day": "tomorrow",
                }
            )

        return chart_data

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
        if self.entity_description.key == "gpe_lowest_price_day":
            # Find the hour with the lowest price during day (6-18)
            lowest_price = self._get_lowest_price_day()
            lowest_hour = None
            if lowest_price is not None and self.coordinator.data:
                for hour in range(6, 18):
                    price_key = f"gpe_price_{hour:02d}"
                    if self.coordinator.data.get(price_key) == lowest_price:
                        lowest_hour = hour
                        break
            return {
                "lowest_price_hour": lowest_hour,
                "time_slot": f"{lowest_hour:02d}:00-{lowest_hour + 1:02d}:00"
                if lowest_hour is not None
                else None,
                "period": "day (06:00-18:00)",
            }
        if self.entity_description.key == "gpe_lowest_price_night":
            # Find the hour with the lowest price during night (18-6)
            lowest_price = self._get_lowest_price_night()
            lowest_hour = None
            if lowest_price is not None and self.coordinator.data:
                # Check evening hours (18-23)
                for hour in range(18, 24):
                    price_key = f"gpe_price_{hour:02d}"
                    if self.coordinator.data.get(price_key) == lowest_price:
                        lowest_hour = hour
                        break
                # Check early morning hours (0-5) if not found
                if lowest_hour is None:
                    for hour in range(6):
                        price_key = f"gpe_price_{hour:02d}"
                        if self.coordinator.data.get(price_key) == lowest_price:
                            lowest_hour = hour
                            break
            return {
                "lowest_price_hour": lowest_hour,
                "time_slot": f"{lowest_hour:02d}:00-{lowest_hour + 1:02d}:00"
                if lowest_hour is not None
                else None,
                "period": "night (18:00-06:00)",
            }
        if self.entity_description.key == "gpe_current_price":
            current_hour = dt_util.now().hour
            return {
                "current_hour": current_hour,
                "time_slot": f"{current_hour:02d}:00-{current_hour + 1:02d}:00",
            }
        if self.entity_description.key == "gpe_price_chart_24h":
            current_hour = dt_util.now().hour
            return {
                "current_hour": current_hour,
                "time_slot": f"{current_hour:02d}:00-{current_hour + 1:02d}:00",
                "data_points": 24,  # Static count instead of dynamic calculation
                "last_updated": dt_util.now().isoformat(),
            }

        return None
