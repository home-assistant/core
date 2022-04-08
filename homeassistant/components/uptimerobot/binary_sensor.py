"""UptimeRobot binary_sensor platform."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UptimeRobotDataUpdateCoordinator
from .const import DOMAIN
from .entity import UptimeRobotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UptimeRobot binary_sensors."""
    coordinator: UptimeRobotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        UptimeRobotBinarySensor(
            coordinator,
            BinarySensorEntityDescription(
                key=str(monitor.id),
                name=monitor.friendly_name,
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
            ),
            monitor=monitor,
        )
        for monitor in coordinator.data
    )


class UptimeRobotBinarySensor(UptimeRobotEntity, BinarySensorEntity):
    """Representation of a UptimeRobot binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return self.monitor_available
