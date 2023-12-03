"""Support for Streamlabs Water Monitor Usage."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, StreamlabsCoordinator

DEPENDENCIES = ["streamlabswater"]

WATER_ICON = "mdi:water"
MIN_TIME_BETWEEN_USAGE_UPDATES = timedelta(seconds=60)

NAME_DAILY_USAGE = "Daily Water"
NAME_MONTHLY_USAGE = "Monthly Water"
NAME_YEARLY_USAGE = "Yearly Water"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_devices: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up water usage sensors."""
    coordinator = hass.data[DOMAIN]

    add_devices(
        [
            StreamLabsDailyUsage(coordinator),
            StreamLabsMonthlyUsage(coordinator),
            StreamLabsYearlyUsage(coordinator),
        ]
    )


class StreamLabsDailyUsage(CoordinatorEntity[StreamlabsCoordinator], SensorEntity):
    """Monitors the daily water usage."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = UnitOfVolume.GALLONS

    @property
    def name(self) -> str:
        """Return the name for daily usage."""
        return f"{self.coordinator.location_name} {NAME_DAILY_USAGE}"

    @property
    def native_value(self) -> float:
        """Return the current daily usage."""
        return self.coordinator.data.daily_usage


class StreamLabsMonthlyUsage(StreamLabsDailyUsage):
    """Monitors the monthly water usage."""

    @property
    def name(self) -> str:
        """Return the name for monthly usage."""
        return f"{self.coordinator.location_name} {NAME_MONTHLY_USAGE}"

    @property
    def native_value(self) -> float:
        """Return the current monthly usage."""
        return self.coordinator.data.monthly_usage


class StreamLabsYearlyUsage(StreamLabsDailyUsage):
    """Monitors the yearly water usage."""

    @property
    def name(self) -> str:
        """Return the name for yearly usage."""
        return f"{self.coordinator.location_name} {NAME_YEARLY_USAGE}"

    @property
    def native_value(self) -> float:
        """Return the current yearly usage."""
        return self.coordinator.data.yearly_usage
