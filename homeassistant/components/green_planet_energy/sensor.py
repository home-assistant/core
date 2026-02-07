"""Green Planet Energy sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from greenplanet_energy_api import GreenPlanetEnergyAPI

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import GreenPlanetEnergyConfigEntry
from .const import DOMAIN
from .coordinator import GreenPlanetEnergyUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class GreenPlanetEnergySensorEntityDescription(SensorEntityDescription):
    """Describes Green Planet Energy sensor entity."""

    value_fn: Callable[[GreenPlanetEnergyAPI, dict[str, Any]], float | datetime | None]


SENSOR_DESCRIPTIONS: list[GreenPlanetEnergySensorEntityDescription] = [
    # Statistical sensors only - hourly prices available via service
    GreenPlanetEnergySensorEntityDescription(
        key="gpe_highest_price_today",
        translation_key="highest_price_today",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=4,
        value_fn=lambda api, data: api.get_highest_price_today(data),
    ),
    GreenPlanetEnergySensorEntityDescription(
        key="gpe_highest_price_time",
        translation_key="highest_price_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda api, data: (
            dt_util.start_of_local_day().replace(hour=hour)
            if (hour := api.get_highest_price_today_with_hour(data)[1]) is not None
            else None
        ),
    ),
    GreenPlanetEnergySensorEntityDescription(
        key="gpe_lowest_price_day",
        translation_key="lowest_price_day",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=4,
        translation_placeholders={"time_range": "(06:00-18:00)"},
        value_fn=lambda api, data: api.get_lowest_price_day(data),
    ),
    GreenPlanetEnergySensorEntityDescription(
        key="gpe_lowest_price_day_time",
        translation_key="lowest_price_day_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_placeholders={"time_range": "(06:00-18:00)"},
        value_fn=lambda api, data: (
            dt_util.start_of_local_day().replace(hour=hour)
            if (hour := api.get_lowest_price_day_with_hour(data)[1]) is not None
            else None
        ),
    ),
    GreenPlanetEnergySensorEntityDescription(
        key="gpe_lowest_price_night",
        translation_key="lowest_price_night",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=4,
        translation_placeholders={"time_range": "(18:00-06:00)"},
        value_fn=lambda api, data: api.get_lowest_price_night(data),
    ),
    GreenPlanetEnergySensorEntityDescription(
        key="gpe_lowest_price_night_time",
        translation_key="lowest_price_night_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_placeholders={"time_range": "(18:00-06:00)"},
        value_fn=lambda api, data: (
            dt_util.start_of_local_day().replace(hour=hour)
            if (hour := api.get_lowest_price_night_with_hour(data)[1]) is not None
            else None
        ),
    ),
    GreenPlanetEnergySensorEntityDescription(
        key="gpe_current_price",
        translation_key="current_price",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_display_precision=4,
        value_fn=lambda api, data: api.get_current_price(data, dt_util.now().hour),
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
        GreenPlanetEnergySensor(coordinator, description)
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
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        # Use fixed unique_id with just the key for predictable entity IDs
        self._attr_unique_id = description.key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="Green Planet Energy",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> float | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.api, self.coordinator.data
        )
