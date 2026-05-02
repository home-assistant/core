"""WJG Sensor Entities."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .coordinator import WJGCameraCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Sensor-Entities fuer einen Config-Entry registrieren."""
    coordinator: WJGCameraCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WJGFileListSensor(coordinator, entry)])


class WJGFileListSensor(CoordinatorEntity[WJGCameraCoordinator], SensorEntity):
    """Sensor für die Dateiliste/SD-Karte der Kamera."""

    _attr_has_entity_name = True
    _attr_name = "Dateiliste"
    _attr_icon = "mdi:folder-multiple"

    def __init__(self, coordinator: WJGCameraCoordinator, entry: ConfigEntry) -> None:
        """Dateilisten-Sensor initialisieren."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_filelist"
        self._attr_native_value = 0
        self._attr_extra_state_attributes = {"files": []}

    @property
    def device_info(self) -> DeviceInfo:
        """Zugehoerige Geraeteinformationen zurueckgeben."""
        return DeviceInfo(identifiers={(DOMAIN, self._entry.entry_id)})

    async def async_update(self) -> None:
        """Dateiliste vom Coordinator abrufen und Attribute aktualisieren."""
        files = await self.coordinator.async_get_file_list()
        self._attr_native_value = len(files)
        self._attr_extra_state_attributes = {"files": files}
