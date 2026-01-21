"""UptimeRobot binary_sensor platform."""

from __future__ import annotations

from pyuptimerobot import UptimeRobotMonitor

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import UptimeRobotConfigEntry
from .entity import UptimeRobotEntity
from .utils import new_device_listener

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UptimeRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the UptimeRobot binary_sensors."""
    coordinator = entry.runtime_data

    def _add_new_entities(new_monitors: list[UptimeRobotMonitor]) -> None:
        """Add entities for new monitors."""
        entities = [
            UptimeRobotBinarySensor(
                coordinator,
                BinarySensorEntityDescription(
                    key=str(monitor.id),
                    device_class=BinarySensorDeviceClass.CONNECTIVITY,
                ),
                monitor=monitor,
            )
            for monitor in new_monitors
        ]
        if entities:
            async_add_entities(entities)

    entry.async_on_unload(new_device_listener(coordinator, _add_new_entities))


class UptimeRobotBinarySensor(UptimeRobotEntity, BinarySensorEntity):
    """Representation of a UptimeRobot binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return bool(self.monitor.status == 2)
