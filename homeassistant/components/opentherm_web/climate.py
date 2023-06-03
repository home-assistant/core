"""Platform for climate integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .opentherm_webapi import OpenThermController


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add climate for passed config_entry in HA."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Add all entities to HA
    async_add_entities(OpenThermClimate(controller) for controller in coordinator.data)


# https://developers.home-assistant.io/docs/core/entity/climate/
class OpenThermClimate(ClimateEntity):
    """Class that represents Climate entity."""

    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.OFF]
    _attr_hvac_mode = HVACMode.AUTO
    _attr_target_temperature_step = 0.1
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    controller: OpenThermController

    def __init__(
        self,
        controller: OpenThermController,
    ) -> None:
        """Initialize."""
        self.controller = controller
        self._attr_unique_id = f"climate_{controller.device_id}"
        self._attr_name = "Thermostat"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, controller.device_id)},
            name="OpenThermWeb",
            manufacturer="Pohorelice",
        )

    async def async_update(self) -> None:
        """Get the latest data."""
        self._attr_current_temperature = self.controller.room_temperature
        self._attr_target_temperature = self.controller.room_setpoint

        if self.controller.enabled:
            self._attr_hvac_mode = HVACMode.AUTO
            if self.controller.chw_active:
                self._attr_icon = "mdi:radiator"
            else:
                self._attr_icon = "mdi:radiator-off"
        else:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_icon = "mdi:radiator-disabled"

        return

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        self.controller.set_room_temperature(temperature)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode not in (HVACMode.AUTO, HVACMode.OFF):
            return

        self.controller.set_hvac_mode(hvac_mode == HVACMode.AUTO)
