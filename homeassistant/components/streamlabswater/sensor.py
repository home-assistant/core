"""Support for Streamlabs Water Monitor Usage."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import StreamlabsCoordinator
from .const import DOMAIN
from .coordinator import StreamlabsData

NAME_DAILY_USAGE = "Daily Water"
NAME_MONTHLY_USAGE = "Monthly Water"
NAME_YEARLY_USAGE = "Yearly Water"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Streamlabs water sensor from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    for location_id in coordinator.data.values():
        entities.extend(
            [
                StreamLabsDailyUsage(coordinator, location_id),
                StreamLabsMonthlyUsage(coordinator, location_id),
                StreamLabsYearlyUsage(coordinator, location_id),
            ]
        )

    async_add_entities(entities)


class StreamLabsDailyUsage(CoordinatorEntity[StreamlabsCoordinator], SensorEntity):
    """Monitors the daily water usage."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS

    def __init__(self, coordinator: StreamlabsCoordinator, location_id: str) -> None:
        """Initialize the daily water usage device."""
        super().__init__(coordinator)
        self._location_id = location_id

    @property
    def location_data(self) -> StreamlabsData:
        """Returns the data object."""
        return self.coordinator.data[self._location_id]

    @property
    def name(self) -> str:
        """Return the name for daily usage."""
        return f"{self.location_data.name} {NAME_DAILY_USAGE}"

    @property
    def native_value(self) -> float:
        """Return the current daily usage."""
        return self.location_data.daily_usage


class StreamLabsMonthlyUsage(StreamLabsDailyUsage):
    """Monitors the monthly water usage."""

    @property
    def name(self) -> str:
        """Return the name for monthly usage."""
        return f"{self.location_data.name} {NAME_MONTHLY_USAGE}"

    @property
    def native_value(self) -> float:
        """Return the current monthly usage."""
        return self.location_data.monthly_usage


class StreamLabsYearlyUsage(StreamLabsDailyUsage):
    """Monitors the yearly water usage."""

    @property
    def name(self) -> str:
        """Return the name for yearly usage."""
        return f"{self.location_data.name} {NAME_YEARLY_USAGE}"

    @property
    def native_value(self) -> float:
        """Return the current yearly usage."""
        return self.location_data.yearly_usage
