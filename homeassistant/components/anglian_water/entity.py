"""Anglian Water entity."""

from __future__ import annotations

import logging

from pyanglianwater.meter import SmartMeter

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AnglianWaterUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class AnglianWaterEntity(CoordinatorEntity[AnglianWaterUpdateCoordinator]):
    """Defines a Anglian Water entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AnglianWaterUpdateCoordinator,
        smart_meter: SmartMeter,
        key: str,
    ) -> None:
        """Initialize Anglian Water entity."""
        super().__init__(coordinator)
        self.smart_meter = smart_meter
        self._attr_unique_id = f"{smart_meter.serial_number}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, smart_meter.serial_number)},
            name=smart_meter.serial_number,
            manufacturer="Anglian Water",
            serial_number=smart_meter.serial_number,
        )

    async def async_added_to_hass(self) -> None:
        """When entity is loaded."""
        self.coordinator.api.updated_data_callbacks.append(self.async_write_ha_state)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """When will be removed from HASS."""
        self.coordinator.api.updated_data_callbacks.remove(self.async_write_ha_state)
        await super().async_will_remove_from_hass()
