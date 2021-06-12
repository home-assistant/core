"""Support for the Brother service."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BrotherDataUpdateCoordinator
from .const import (
    ATTR_COUNTER,
    ATTR_ENABLED,
    ATTR_LABEL,
    ATTR_MANUFACTURER,
    ATTR_REMAINING_PAGES,
    ATTR_UNIT,
    ATTR_UPTIME,
    ATTRS_MAP,
    DATA_CONFIG_ENTRY,
    DOMAIN,
    SENSOR_TYPES,
)


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

    for sensor in SENSOR_TYPES:
        if sensor in coordinator.data:
            sensors.append(BrotherPrinterSensor(coordinator, sensor, device_info))
    async_add_entities(sensors, False)


class BrotherPrinterSensor(CoordinatorEntity, SensorEntity):
    """Define an Brother Printer sensor."""

    def __init__(
        self,
        coordinator: BrotherDataUpdateCoordinator,
        kind: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        description = SENSOR_TYPES[kind]
        self._attrs: dict[str, Any] = {}
        self._attr_device_class = description.get(ATTR_DEVICE_CLASS)
        self._attr_device_info = device_info
        self._attr_entity_registry_enabled_default = description[ATTR_ENABLED]
        self._attr_icon = description[ATTR_ICON]
        self._attr_name = f"{coordinator.data.model} {description[ATTR_LABEL]}"
        self._attr_state_class = description[ATTR_STATE_CLASS]
        self._attr_unique_id = f"{coordinator.data.serial.lower()}_{kind}"
        self._attr_unit_of_measurement = description[ATTR_UNIT]
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
