"""Support for the Nettigo Air Monitor service."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow

from . import NAMDataUpdateCoordinator
from .const import ATTR_ENABLED, ATTR_LABEL, ATTR_UNIT, ATTR_UPTIME, DOMAIN, SENSORS

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a Nettigo Air Monitor entities from a config_entry."""
    coordinator: NAMDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors: list[NAMSensor | NAMSensorUptime] = []
    for sensor in SENSORS:
        if sensor in coordinator.data:
            if sensor == ATTR_UPTIME:
                sensors.append(NAMSensorUptime(coordinator, sensor))
            else:
                sensors.append(NAMSensor(coordinator, sensor))

    async_add_entities(sensors, False)


class NAMSensor(CoordinatorEntity, SensorEntity):
    """Define an Nettigo Air Monitor sensor."""

    coordinator: NAMDataUpdateCoordinator

    def __init__(self, coordinator: NAMDataUpdateCoordinator, sensor_type: str) -> None:
        """Initialize."""
        super().__init__(coordinator)
        description = SENSORS[sensor_type]
        self._attr_device_class = description[ATTR_DEVICE_CLASS]
        self._attr_device_info = coordinator.device_info
        self._attr_entity_registry_enabled_default = description[ATTR_ENABLED]
        self._attr_icon = description[ATTR_ICON]
        self._attr_name = description[ATTR_LABEL]
        self._attr_state_class = description[ATTR_STATE_CLASS]
        self._attr_unique_id = f"{coordinator.unique_id}-{sensor_type}"
        self._attr_unit_of_measurement = description[ATTR_UNIT]
        self.sensor_type = sensor_type

    @property
    def state(self) -> Any:
        """Return the state."""
        return getattr(self.coordinator.data, self.sensor_type)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        available = super().available

        # For a short time after booting, the device does not return values for all
        # sensors. For this reason, we mark entities for which data is missing as
        # unavailable.
        return available and bool(
            getattr(self.coordinator.data, self.sensor_type, None)
        )


class NAMSensorUptime(NAMSensor):
    """Define an Nettigo Air Monitor uptime sensor."""

    @property
    def state(self) -> str:
        """Return the state."""
        uptime_sec = getattr(self.coordinator.data, self.sensor_type)
        return (
            (utcnow() - timedelta(seconds=uptime_sec))
            .replace(microsecond=0)
            .isoformat()
        )
