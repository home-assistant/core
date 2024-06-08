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
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import MODBUS_REGISTERS

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
        self._attr_max_temp = 70
        self._attr_min_temp = 30
        self._attr_precision = PRECISION_WHOLE
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
        name = self.name if isinstance(self.name, str) else None
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": name,
            "model": "x-buffer",
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

    @property
    def translation_key(self):
        """Return the translation key."""
        return "kermi_water_heater"

    async def write_register(self, register, value):
        """Write a register value to the device."""
        client = self.hass.data[DOMAIN][self.entry.entry_id]["client"]
        result = await client.write_register(
            register, value, self.entry.data["water_heater_device_address"]
        )
        logger.debug("Value set via modbus: %s", result)
        return result

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            # Get the register info for the target temperature, only the constant one is writeable
            register_info = MODBUS_REGISTERS["water_heater"][
                "constant_target_temperature"
            ]

            # Scale the temperature according to the scale_factor
            scaled_temperature = int(temperature / register_info["scale_factor"])

            # Schedule the function to be run on the event loop
            self.hass.add_job(
                self.write_register, register_info["register"], scaled_temperature
            )

        self._attr_target_temperature = temperature
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        if operation_mode is not None:
            # Get the register info for the operation_mode
            register_info = MODBUS_REGISTERS["water_heater"]["operation_mode"]

            mapped_mode = {v: k for k, v in register_info["mapping"].items()}[  # type: ignore[attr-defined]
                operation_mode
            ]

            # Schedule the function to be run on the event loop
            self.hass.add_job(
                self.write_register, register_info["register"], mapped_mode
            )

        self._attr_current_operation = operation_mode
        self.schedule_update_ha_state()
