"""UptimeRobot sensor platform."""
from __future__ import annotations

from typing import TypedDict

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UptimeRobotDataUpdateCoordinator
from .const import DOMAIN
from .entity import UptimeRobotEntity


class StatusValue(TypedDict):
    """Sensor details."""

    value: str
    icon: str


SENSORS_INFO = {
    0: StatusValue(value="pause", icon="mdi:television-pause"),
    1: StatusValue(value="not_checked_yet", icon="mdi:television"),
    2: StatusValue(value="up", icon="mdi:television-shimmer"),
    8: StatusValue(value="seems_down", icon="mdi:television-off"),
    9: StatusValue(value="down", icon="mdi:television-off"),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UptimeRobot sensors."""
    coordinator: UptimeRobotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        UptimeRobotSensor(
            coordinator,
            SensorEntityDescription(
                key=str(monitor.id),
                name=monitor.friendly_name,
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
        return SENSORS_INFO[self.monitor.status]["value"]

    @property
    def icon(self) -> str:
        """Return the status of the monitor."""
        return SENSORS_INFO[self.monitor.status]["icon"]
