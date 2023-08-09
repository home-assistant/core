"""Platform for climate integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OpenThermWebCoordinator
from .const import DOMAIN
from .opentherm_controller import OpenThermController
from .opentherm_web_api import OpenThermWebApi


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
    async_add_entities(
        OpenThermClimate(coordinator, web_api) for web_api in coordinator.data
    )


# https://developers.home-assistant.io/docs/core/entity/climate/
class OpenThermClimate(CoordinatorEntity[OpenThermWebCoordinator], ClimateEntity):
    """Class that represents Climate entity."""

    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.OFF]
    _attr_hvac_mode = HVACMode.AUTO
    _attr_target_temperature_step = 0.1
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    controller: OpenThermController
    web_api: OpenThermWebApi

    def __init__(
        self,
        coordinator: OpenThermWebCoordinator,
        web_api: OpenThermWebApi,
    ) -> None:
        """Initialize Climate Entity."""
        super().__init__(coordinator, context=web_api)
        self.web_api = web_api
        self.controller = web_api.get_controller()
        self._attr_unique_id = f"climate_{self.controller.device_id}"
        self._attr_name = "Thermostat"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.controller.device_id)},
            name="OpenThermWeb",
            manufacturer="Lake292",
        )
        self.refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.refresh()
        super()._handle_coordinator_update()

    def refresh(self) -> None:
        """Handle updated data from the coordinator."""
        self.controller = self.coordinator.data.web_api.get_controller()
        self._attr_current_temperature = self.controller.room_temperature
        self._attr_target_temperature = self.controller.room_setpoint

        if not self.controller.chw_away:
            self._attr_hvac_mode = HVACMode.AUTO
            if self.controller.chw_active:
                self._attr_icon = "mdi:radiator"
                self._attr_hvac_action = HVACAction.HEATING
            else:
                self._attr_icon = "mdi:radiator-off"
                self._attr_hvac_action = HVACAction.IDLE
        else:
            self._attr_hvac_mode = HVACMode.OFF
            self._attr_hvac_action = HVACAction.OFF
            self._attr_icon = "mdi:radiator-disabled"

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        self.web_api.set_room_temperature(temperature)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode not in (HVACMode.AUTO, HVACMode.OFF):
            return

        self.web_api.set_hvac_mode(hvac_mode == HVACMode.AUTO)
