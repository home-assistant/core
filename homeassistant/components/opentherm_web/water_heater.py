"""Platform for water heater integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import (
    STATE_GAS,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
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
    """Add water_heater for passed config_entry in HA."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Add all entities to HA
    async_add_entities(
        OpenThermWaterHeater(hass, coordinator, web_api) for web_api in coordinator.data
    )


# https://developers.home-assistant.io/docs/core/entity/water-heater/
class OpenThermWaterHeater(
    CoordinatorEntity[OpenThermWebCoordinator], WaterHeaterEntity
):
    """Class that represents WaterHeater entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.AWAY_MODE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )
    _attr_operation_list = [STATE_GAS]

    controller: OpenThermController
    web_api: OpenThermWebApi
    hass: HomeAssistant

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: OpenThermWebCoordinator,
        web_api: OpenThermWebApi,
    ) -> None:
        """Initiatlize WaterHeater entity."""
        super().__init__(coordinator, context=web_api)
        self.hass = hass
        self.web_api = web_api
        self.controller = web_api.get_controller()
        self._attr_unique_id = f"water_heater_{self.controller.device_id}"
        self._attr_name = "Water Heater"
        self._attr_current_operation = STATE_GAS
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.controller.device_id)},
            name="OpenThermWeb",
            manufacturer="Pohorelice",
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
        if self.controller.dhw_away or self.controller.dhw_setpoint == 0:
            self._attr_icon = "mdi:water-boiler-off"
        else:
            self._attr_icon = "mdi:water-boiler-auto"

        self._attr_current_temperature = self.controller.dhw_temperature
        self._attr_target_temperature = self.controller.dhw_setpoint
        self._attr_is_away_mode_on = self.controller.dhw_away

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        self.web_api.set_dhw_temperature(temperature)

    def turn_away_mode_on(self) -> None:
        """Turn on away mode."""
        self.web_api.set_dhw_away_mode(True)

    def turn_away_mode_off(self) -> None:
        """Turn off away mode."""
        self.web_api.set_dhw_away_mode(False)

    async def async_turn_on(self) -> None:
        """Turn on."""
        await self.hass.async_add_executor_job(self.turn_away_mode_off)

    async def async_turn_off(self) -> None:
        """Turn off."""
        await self.hass.async_add_executor_job(self.turn_away_mode_on)
