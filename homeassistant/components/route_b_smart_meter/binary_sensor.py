"""Binary sensors for the Smart Meter B Route integration."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BRouteConfigEntry
from .const import ATTR_API_FAULT_STATUS, DOMAIN
from .coordinator import BRouteUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BRouteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Smart Meter B-route binary sensor entry."""
    coordinator = entry.runtime_data

    async_add_entities([SmartMeterBRouteFaultSensor(coordinator)])


class SmartMeterBRouteFaultSensor(
    CoordinatorEntity[BRouteUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Smart Meter B-route fault status sensor."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = ATTR_API_FAULT_STATUS

    def __init__(
        self,
        coordinator: BRouteUpdateCoordinator,
    ) -> None:
        """Initialize Smart Meter B-route fault sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.bid}_{ATTR_API_FAULT_STATUS}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.bid)},
            name=f"Route B Smart Meter {coordinator.bid}",
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if a fault is detected."""
        return self.coordinator.data.fault_status
