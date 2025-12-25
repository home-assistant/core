"""UptimeRobot sensor platform."""

from __future__ import annotations

from pyuptimerobot import UptimeRobotMonitor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
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
    """Set up the UptimeRobot sensors."""
    coordinator = entry.runtime_data

    def _add_new_entities(new_monitors: list[UptimeRobotMonitor]) -> None:
        """Add entities for new monitors."""
        entities = [
            UptimeRobotSensor(
                coordinator,
                SensorEntityDescription(
                    key=str(monitor.id),
                    entity_category=EntityCategory.DIAGNOSTIC,
                    device_class=SensorDeviceClass.ENUM,
                    options=[
                        "down",
                        "not_checked_yet",
                        "paused",
                        "seems_down",
                        "up",
                    ],
                    translation_key="monitor_status",
                ),
                monitor=monitor,
            )
            for monitor in new_monitors
        ]
        if entities:
            async_add_entities(entities)

    entry.async_on_unload(new_device_listener(coordinator, _add_new_entities))


class UptimeRobotSensor(UptimeRobotEntity, SensorEntity):
    """Representation of a UptimeRobot sensor."""

    @property
    def native_value(self) -> str:
        """Return the status of the monitor."""
        return self.monitor.status.lower()  # type: ignore[no-any-return]
