"""Green Planet Energy sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import GreenPlanetEnergyConfigEntry
from .coordinator import GreenPlanetEnergyUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def get_highest_price_today(data: dict[str, Any]) -> float | None:
    """Get the highest price from today's data."""
    if not data:
        return None

    prices = []
    for hour in range(24):
        price_key = f"gpe_price_{hour:02d}"
        if price_key in data:
            price = data[price_key]
            if price is not None:
                prices.append(price)

    return max(prices) if prices else None


def get_lowest_price_day(data: dict[str, Any]) -> float | None:
    """Get the lowest price during day hours (6-18)."""
    if not data:
        return None

    prices = []
    for hour in range(6, 18):  # Day period: 6:00 to 18:00
        price_key = f"gpe_price_{hour:02d}"
        if price_key in data:
            price = data[price_key]
            if price is not None:
                prices.append(price)

    return min(prices) if prices else None


def get_lowest_price_night(data: dict[str, Any]) -> float | None:
    """Get the lowest price during night hours (18-6)."""
    if not data:
        return None

    prices = []
    # Evening hours (18-23)
    for hour in range(18, 24):
        price_key = f"gpe_price_{hour:02d}"
        if price_key in data:
            price = data[price_key]
            if price is not None:
                prices.append(price)

    # Early morning hours (0-5)
    for hour in range(6):
        price_key = f"gpe_price_{hour:02d}"
        if price_key in data:
            price = data[price_key]
            if price is not None:
                prices.append(price)

    return min(prices) if prices else None


def get_current_price(data: dict[str, Any]) -> float | None:
    """Get the price for the current hour."""
    if not data:
        return None

    current_hour = dt_util.now().hour
    price_key = f"gpe_price_{current_hour:02d}"
    return data.get(price_key)


@dataclass(frozen=True, kw_only=True)
class GreenPlanetEnergySensorEntityDescription(SensorEntityDescription):
    """Describes Green Planet Energy sensor entity."""

    value_fn: Callable[[dict[str, Any]], float | None]


SENSOR_DESCRIPTIONS: list[GreenPlanetEnergySensorEntityDescription] = [
    # Statistical sensors only - hourly prices available via service
    GreenPlanetEnergySensorEntityDescription(
        key="gpe_highest_price_today",
        translation_key="highest_price_today",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=4,
        value_fn=get_highest_price_today,
    ),
    GreenPlanetEnergySensorEntityDescription(
        key="gpe_lowest_price_day",
        translation_key="lowest_price_day",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=4,
        value_fn=get_lowest_price_day,
    ),
    GreenPlanetEnergySensorEntityDescription(
        key="gpe_lowest_price_night",
        translation_key="lowest_price_night",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=4,
        value_fn=get_lowest_price_night,
    ),
    GreenPlanetEnergySensorEntityDescription(
        key="gpe_current_price",
        translation_key="current_price",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=4,
        value_fn=get_current_price,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GreenPlanetEnergyConfigEntry,
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
        config_entry: GreenPlanetEnergyConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        # Use fixed unique_id with just the key for predictable entity IDs
        self._attr_unique_id = description.key

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if self.entity_description.key == "gpe_highest_price_today":
            # Find the hour with the highest price
            highest_price = get_highest_price_today(self.coordinator.data)
            highest_hour = None
            if highest_price is not None and self.coordinator.data:
                for hour in range(24):
                    price_key = f"gpe_price_{hour:02d}"
                    if self.coordinator.data.get(price_key) == highest_price:
                        highest_hour = hour
                        break
            return {
                "time_slot": f"{highest_hour:02d}:00-{highest_hour + 1:02d}:00"
                if highest_hour is not None
                else None,
            }

        if self.entity_description.key == "gpe_lowest_price_day":
            # Find the hour with the lowest price during day (6-18)
            lowest_price = get_lowest_price_day(self.coordinator.data)
            lowest_hour = None
            if lowest_price is not None and self.coordinator.data:
                for hour in range(6, 18):
                    price_key = f"gpe_price_{hour:02d}"
                    if self.coordinator.data.get(price_key) == lowest_price:
                        lowest_hour = hour
                        break
            return {
                "time_slot": f"{lowest_hour:02d}:00-{lowest_hour + 1:02d}:00"
                if lowest_hour is not None
                else None,
            }

        if self.entity_description.key == "gpe_lowest_price_night":
            # Find the hour with the lowest price during night (18-6)
            lowest_price = get_lowest_price_night(self.coordinator.data)
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
                "time_slot": f"{lowest_hour:02d}:00-{lowest_hour + 1:02d}:00"
                if lowest_hour is not None
                else None,
            }

        if self.entity_description.key == "gpe_current_price":
            current_hour = dt_util.now().hour
            return {
                "time_slot": f"{current_hour:02d}:00-{current_hour + 1:02d}:00",
            }

        return None
