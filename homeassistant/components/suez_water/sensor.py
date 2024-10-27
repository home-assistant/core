"""Sensor for Suez Water Consumption data."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
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
    async_add_entities([SuezAggregatedSensor(coordinator, entry.data[CONF_COUNTER_ID])])


class SuezAggregatedSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "water_usage_yesterday"
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_device_class = SensorDeviceClass.WATER

    def __init__(self, coordinator: SuezWaterCoordinator, counter_id: int) -> None:
        """Initialize the data object."""
        super().__init__(coordinator, context=counter_id)
        self.coordinator: SuezWaterCoordinator = coordinator
        self._attr_extra_state_attributes = {}
        self._attr_unique_id = f"{counter_id}_water_usage_yesterday"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(counter_id))},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Suez",
        )

    @property
    def native_value(self) -> float | None:
        """Return the current daily usage."""
        if self.coordinator.aggregated_data is None:
            return None
        return self.coordinator.aggregated_data.value

    @property
    def attribution(self) -> None | str:
        """Return data attribution message."""
        if self.coordinator.aggregated_data is None:
            return None
        return self.coordinator.aggregated_data.attribution

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return aggregated data."""
        if self.coordinator.aggregated_data is None:
            return None
        return {
            "this_month_consumption": self.coordinator.aggregated_data.currentMonth,
            "previous_month_consumption": self.coordinator.aggregated_data.previousMonth,
            "highest_monthly_consumption": self.coordinator.aggregated_data.highestMonthlyConsumption,
            "last_year_overall": self.coordinator.aggregated_data.previousYear,
            "this_year_overall": self.coordinator.aggregated_data.currentYear,
            "history": self.coordinator.aggregated_data.history,
        }
