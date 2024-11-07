"""Sensor for Suez Water Consumption data."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CURRENCY_EURO, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_COUNTER_ID, DOMAIN
from .coordinator import SuezWaterCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Suez Water sensor from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    counter_id = entry.data[CONF_COUNTER_ID]
    async_add_entities(
        [
            SuezAggregatedSensor(coordinator, counter_id),
            SuezPriceSensor(coordinator, counter_id),
        ]
    )


class _SuezSensor(CoordinatorEntity[SuezWaterCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SuezWaterCoordinator, counter_id: int, name: str
    ) -> None:
        """Initialize the data object."""
        super().__init__(coordinator)
        self._attr_translation_key = name
        self._attr_unique_id = f"{counter_id}_{name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(counter_id))},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Suez",
        )


class SuezAggregatedSensor(_SuezSensor):
    """Representation of a Sensor."""

    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_device_class = SensorDeviceClass.WATER

    def __init__(self, coordinator: SuezWaterCoordinator, counter_id: int) -> None:
        """Initialize the data object."""
        super().__init__(coordinator, counter_id, "water_usage_yesterday")

    @property
    def native_value(self) -> float:
        """Return the current daily usage."""
        return self.coordinator.data.aggregated.value

    @property
    def attribution(self) -> str:
        """Return data attribution message."""
        return self.coordinator.data.aggregated.attribution

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return aggregated data."""
        return {
            "this_month_consumption": self.coordinator.data.aggregated.current_month,
            "previous_month_consumption": self.coordinator.data.aggregated.previous_month,
            "highest_monthly_consumption": self.coordinator.data.aggregated.highest_monthly_consumption,
            "last_year_overall": self.coordinator.data.aggregated.previous_year,
            "this_year_overall": self.coordinator.data.aggregated.current_year,
            "history": self.coordinator.data.aggregated.history,
        }


class SuezPriceSensor(_SuezSensor):
    """Reprensation of water price."""

    _attr_native_unit_of_measurement = CURRENCY_EURO
    _attr_device_class = SensorDeviceClass.MONETARY

    def __init__(self, coordinator: SuezWaterCoordinator, counter_id: int) -> None:
        """Initialize the data object."""
        super().__init__(coordinator, counter_id, "water_price")

    @property
    def native_value(self) -> float:
        """Return the current water price."""
        return self.coordinator.data.price.price
