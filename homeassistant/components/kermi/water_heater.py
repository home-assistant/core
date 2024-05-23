"""Kermi Water Heater accessed via an IFM modbus gateway."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import water_heater
from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

SUPPORT_FLAGS_HEATER = (
    WaterHeaterEntityFeature.TARGET_TEMPERATURE
    | WaterHeaterEntityFeature.OPERATION_MODE
)

DOMAIN = "kermi"
logger = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the config entry."""
    kermi_water_heater = KermiWaterHeater(
        "Kermi x-buffer",
        entry,
        hass.data[DOMAIN][entry.entry_id]["coordinator"],
    )
    async_add_entities([kermi_water_heater])


class KermiWaterHeater(WaterHeaterEntity, CoordinatorEntity):
    """Representation of water_heater device attached to IFM."""

    _attr_should_poll = False
    _attr_supported_features = SUPPORT_FLAGS_HEATER

    def __init__(
        self,
        name: str,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the water_heater device."""
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_target_temperature = 0
        # kermi always returns celsius
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_current_operation = "auto"
        self._attr_operation_list = [
            water_heater.const.STATE_HEAT_PUMP,
            water_heater.const.STATE_PERFORMANCE,
            water_heater.const.STATE_ELECTRIC,
            water_heater.const.STATE_HIGH_DEMAND,
            "auto",
        ]
        self.entry = entry
        self._entry_id = entry.entry_id

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": "Kermi Water Heater",
            "model": "x-change dynamic pro ac",
            "manufacturer": "Kermi",
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.hass.data[DOMAIN][self._entry_id]["coordinator"].data
        self._attr_current_temperature = data.get("water_heater_temperature")
        self._attr_target_temperature = data.get("water_heater_target_temperature")
        self._attr_current_operation = data.get("water_heater_operation_mode")
        self.async_write_ha_state()

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"{self._entry_id}_{self.entry.data['water_heater_device_address']}"

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        self._attr_target_temperature = kwargs.get(ATTR_TEMPERATURE)
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        self._attr_current_operation = operation_mode
        self.schedule_update_ha_state()
