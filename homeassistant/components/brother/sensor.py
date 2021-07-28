"""Support for the Brother service."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
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

    for description in SENSOR_TYPES:
        if description.key in coordinator.data:
            sensors.append(BrotherPrinterSensor(coordinator, description, device_info))
    async_add_entities(sensors, False)


class BrotherPrinterSensor(CoordinatorEntity, SensorEntity):
    """Define an Brother Printer sensor."""

    def __init__(
        self,
        coordinator: BrotherDataUpdateCoordinator,
        description: SensorEntityDescription,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attrs: dict[str, Any] = {}
        self._attr_device_info = device_info
        self._attr_name = f"{coordinator.data.model} {description.name}"
        self._attr_unique_id = f"{coordinator.data.serial.lower()}_{description.key}"
        self.entity_description = description

    @property
    def state(self) -> StateType:
        """Return the state."""
        if self.entity_description.key == ATTR_UPTIME:
            return cast(
                StateType,
                getattr(self.coordinator.data, self.entity_description.key).isoformat(),
            )
        return cast(
            StateType, getattr(self.coordinator.data, self.entity_description.key)
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        remaining_pages, drum_counter = ATTRS_MAP.get(
            self.entity_description.key, (None, None)
        )
        if remaining_pages and drum_counter:
            self._attrs[ATTR_REMAINING_PAGES] = getattr(
                self.coordinator.data, remaining_pages
            )
            self._attrs[ATTR_COUNTER] = getattr(self.coordinator.data, drum_counter)
        return self._attrs
