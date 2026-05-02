"""WJG Binary Sensor Entities."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .coordinator import WJGCameraCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Binary-Sensor-Entities fuer einen Config-Entry registrieren."""
    coordinator: WJGCameraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WJGMotionSensor(coordinator, entry)])


class WJGMotionSensor(CoordinatorEntity[WJGCameraCoordinator], BinarySensorEntity):
    """Bewegungserkennungs-Sensor."""
    _attr_has_entity_name = True
    _attr_name = "Bewegung"
    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator: WJGCameraCoordinator, entry: ConfigEntry) -> None:
        """Bewegungssensor initialisieren."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_motion"

    @property
    def device_info(self) -> DeviceInfo:
        """Zugehoerige Geraeteinformationen zurueckgeben."""
        return DeviceInfo(identifiers={(DOMAIN, self._entry.entry_id)})

    @property
    def is_on(self) -> bool:
        """Bewegungsstatus des Coordinators liefern."""
        return self.coordinator.motion_detected

    @property
    def extra_state_attributes(self) -> dict[str, float]:
        """Zeitpunkt der letzten erkannten Bewegung exponieren."""
        return {"last_motion": self.coordinator.last_motion_time}
