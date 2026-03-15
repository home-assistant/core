"""Sensor platform for Met Office Weather Warnings."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    MetOfficeWarningsConfigEntry,
    MetOfficeWarningsCoordinator,
    MetOfficeWarningsData,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MetOfficeWarningsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Met Office Weather Warnings sensor."""
    coordinator = entry.runtime_data
    async_add_entities([MetOfficeWarningsSensor(coordinator, entry)])


class MetOfficeWarningsSensor(
    CoordinatorEntity[MetOfficeWarningsCoordinator], SensorEntity
):
    """Sensor for Met Office weather warnings."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_has_entity_name = True
    _attr_translation_key = "warnings"

    def __init__(
        self,
        coordinator: MetOfficeWarningsCoordinator,
        entry: MetOfficeWarningsConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_warnings"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Met Office",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the last updated time of the feed."""
        data: MetOfficeWarningsData | None = self.coordinator.data
        if data is None:
            return None
        return data.pub_date

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return warning details as attributes."""
        data: MetOfficeWarningsData | None = self.coordinator.data
        if data is None or not data.warnings:
            return None
        return {"warnings": [asdict(w) for w in data.warnings]}
