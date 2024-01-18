"""Sensor for Home Assistant analytics."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AnalyticsData
from .const import DOMAIN
from .coordinator import HomeassistantAnalyticsDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize the entries."""

    analytics_data: AnalyticsData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HomeassistantAnalyticsSensor(
            analytics_data.coordinator,
            integration_domain,
            analytics_data.names[integration_domain],
        )
        for integration_domain in analytics_data.coordinator.data
    )


class HomeassistantAnalyticsSensor(
    CoordinatorEntity[HomeassistantAnalyticsDataUpdateCoordinator], SensorEntity
):
    """Home Assistant Analytics Sensor."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "active installations"

    def __init__(
        self,
        coordinator: HomeassistantAnalyticsDataUpdateCoordinator,
        integration_domain: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"core_{integration_domain}_active_installations"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            entry_type=DeviceEntryType.SERVICE,
        )
        self._integration_domain = integration_domain

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get(self._integration_domain)
