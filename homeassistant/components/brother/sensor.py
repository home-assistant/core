"""Support for the Brother service."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BrotherDataUpdateCoordinator
from .const import (
    ATTR_COUNTER,
    ATTR_MANUFACTURER,
    ATTR_REMAINING_PAGES,
    ATTR_UPTIME,
    ATTRS_MAP,
    DATA_CONFIG_ENTRY,
    DOMAIN,
    SENSOR_TYPES,
)
from .model import BrotherSensorMetadata


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Brother entities from a config_entry."""
    coordinator = hass.data[DOMAIN][DATA_CONFIG_ENTRY][entry.entry_id]

    sensors = []

    device_info: DeviceInfo = {
        "identifiers": {(DOMAIN, coordinator.data.serial)},
        "name": coordinator.data.model,
        "manufacturer": ATTR_MANUFACTURER,
        "model": coordinator.data.model,
        "sw_version": getattr(coordinator.data, "firmware", None),
    }

    for sensor, metadata in SENSOR_TYPES.items():
        if sensor in coordinator.data:
            sensors.append(
                BrotherPrinterSensor(coordinator, sensor, metadata, device_info)
            )
    async_add_entities(sensors, False)


class BrotherPrinterSensor(CoordinatorEntity, SensorEntity):
    """Define an Brother Printer sensor."""

    def __init__(
        self,
        coordinator: BrotherDataUpdateCoordinator,
        kind: str,
        metadata: BrotherSensorMetadata,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attrs: dict[str, Any] = {}
        self._attr_device_class = metadata.device_class
        self._attr_device_info = device_info
        self._attr_entity_registry_enabled_default = metadata.enabled
        self._attr_icon = metadata.icon
        self._attr_name = f"{coordinator.data.model} {metadata.label}"
        self._attr_state_class = metadata.state_class
        self._attr_unique_id = f"{coordinator.data.serial.lower()}_{kind}"
        self._attr_unit_of_measurement = metadata.unit_of_measurement
        self.kind = kind

    @property
    def state(self) -> Any:
        """Return the state."""
        if self.kind == ATTR_UPTIME:
            return getattr(self.coordinator.data, self.kind).isoformat()
        return getattr(self.coordinator.data, self.kind)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        remaining_pages, drum_counter = ATTRS_MAP.get(self.kind, (None, None))
        if remaining_pages and drum_counter:
            self._attrs[ATTR_REMAINING_PAGES] = getattr(
                self.coordinator.data, remaining_pages
            )
            self._attrs[ATTR_COUNTER] = getattr(self.coordinator.data, drum_counter)
        return self._attrs
