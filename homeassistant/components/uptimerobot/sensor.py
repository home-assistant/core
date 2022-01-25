"""UptimeRobot sensor platform."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .entity import UptimeRobotEntity

SENSORS_INFO = {
    "0": {"state": "Pause", "icon": "mdi:television-pause"},
    "1": {"state": "Not checked yet", "icon": "mdi:television"},
    "2": {"state": "Up", "icon": "mdi:television-shimmer"},
    "8": {"state": "Seems down", "icon": "mdi:television-off"},
    "9": {"state": "Down", "icon": "mdi:television-off"},
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the UptimeRobot sensors."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            UptimeRobotSensor(
                coordinator,
                SensorEntityDescription(
                    key=str(monitor.id),
                    name=monitor.friendly_name,
                ),
                monitor=monitor,
            )
            for monitor in coordinator.data
        ],
    )


class UptimeRobotSensor(UptimeRobotEntity, SensorEntity):
    """Representation of a UptimeRobot sensor."""

    @property
    def native_value(self) -> str:
        """Return the status of the monitor."""
        return SENSORS_INFO[str(self.monitor.status)]["state"]

    @property
    def icon(self) -> str:
        """Return the status of the monitor."""
        return SENSORS_INFO[str(self.monitor.status)]["icon"]
