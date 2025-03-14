"""UptimeRobot sensor platform."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import UptimeRobotDataUpdateCoordinator
from .entity import UptimeRobotEntity

SENSORS_INFO = {
    0: "pause",
    1: "not_checked_yet",
    2: "up",
    8: "seems_down",
    9: "down",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the UptimeRobot sensors."""
    coordinator: UptimeRobotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        UptimeRobotSensor(
            coordinator,
            SensorEntityDescription(
                key=str(monitor.id),
                entity_category=EntityCategory.DIAGNOSTIC,
                device_class=SensorDeviceClass.ENUM,
                options=["down", "not_checked_yet", "pause", "seems_down", "up"],
                translation_key="monitor_status",
            ),
            monitor=monitor,
        )
        for monitor in coordinator.data
    )


class UptimeRobotSensor(UptimeRobotEntity, SensorEntity):
    """Representation of a UptimeRobot sensor."""

    @property
    def native_value(self) -> str:
        """Return the status of the monitor."""
        return SENSORS_INFO[self.monitor.status]
