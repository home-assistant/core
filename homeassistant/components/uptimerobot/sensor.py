"""UptimeRobot sensor platform."""

from __future__ import annotations

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

SENSORS_INFO = {
    0: "pause",
    1: "not_checked_yet",
    2: "up",
    8: "seems_down",
    9: "down",
}

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UptimeRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the UptimeRobot sensors."""
    coordinator = entry.runtime_data

    known_devices: set[int] = set()

    def _check_device() -> None:
        entities: list[UptimeRobotSensor] = []
        for monitor in coordinator.data:
            if monitor.id in known_devices:
                continue
            known_devices.add(monitor.id)
            entities.append(
                UptimeRobotSensor(
                    coordinator,
                    SensorEntityDescription(
                        key=str(monitor.id),
                        entity_category=EntityCategory.DIAGNOSTIC,
                        device_class=SensorDeviceClass.ENUM,
                        options=[
                            "down",
                            "not_checked_yet",
                            "pause",
                            "seems_down",
                            "up",
                        ],
                        translation_key="monitor_status",
                    ),
                    monitor=monitor,
                )
            )
        if entities:
            async_add_entities(entities)

    _check_device()
    entry.async_on_unload(coordinator.async_add_listener(_check_device))


class UptimeRobotSensor(UptimeRobotEntity, SensorEntity):
    """Representation of a UptimeRobot sensor."""

    @property
    def native_value(self) -> str:
        """Return the status of the monitor."""
        return SENSORS_INFO[self.monitor.status]
