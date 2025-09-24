"""UptimeRobot binary_sensor platform."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import UptimeRobotConfigEntry
from .entity import UptimeRobotEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UptimeRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the UptimeRobot binary_sensors."""
    coordinator = entry.runtime_data

    known_devices: set[int] = set()

    def _check_device() -> None:
        current_devices = {monitor.id for monitor in coordinator.data}
        new_devices = current_devices - known_devices
        if new_devices:
            known_devices.update(new_devices)
            async_add_entities(
                UptimeRobotBinarySensor(
                    coordinator,
                    BinarySensorEntityDescription(
                        key=str(monitor.id),
                        device_class=BinarySensorDeviceClass.CONNECTIVITY,
                    ),
                    monitor=monitor,
                )
                for monitor in coordinator.data
                if monitor.id in new_devices
            )

    _check_device()
    entry.async_on_unload(coordinator.async_add_listener(_check_device))


class UptimeRobotBinarySensor(UptimeRobotEntity, BinarySensorEntity):
    """Representation of a UptimeRobot binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return bool(self.monitor.status == 2)
