"""Support for the Airzone climate."""
from __future__ import annotations

import logging
from typing import Any, Final

from aioairzone.common import OperationMode
from aioairzone.const import (
    API_MODE,
    API_ON,
    API_SET_POINT,
    API_SYSTEM_ID,
    API_ZONE_ID,
    AZD_DEMAND,
    AZD_HUMIDITY,
    AZD_MASTER,
    AZD_MODE,
    AZD_MODES,
    AZD_NAME,
    AZD_ON,
    AZD_TEMP,
    AZD_TEMP_MAX,
    AZD_TEMP_MIN,
    AZD_TEMP_SET,
    AZD_TEMP_UNIT,
    AZD_ZONES,
)
from aioairzone.exceptions import AirzoneError

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import API_TEMPERATURE_STEP, DOMAIN, TEMP_UNIT_LIB_TO_HASS
from .coordinator import AirzoneUpdateCoordinator
from .entity import AirzoneZoneEntity

_LOGGER = logging.getLogger(__name__)


HVAC_ACTION_LIB_TO_HASS: Final[dict[OperationMode, HVACAction]] = {
    OperationMode.STOP: HVACAction.OFF,
    OperationMode.COOLING: HVACAction.COOLING,
    OperationMode.HEATING: HVACAction.HEATING,
    OperationMode.FAN: HVACAction.FAN,
    OperationMode.DRY: HVACAction.DRYING,
}
HVAC_MODE_LIB_TO_HASS: Final[dict[OperationMode, HVACMode]] = {
    OperationMode.STOP: HVACMode.OFF,
    OperationMode.COOLING: HVACMode.COOL,
    OperationMode.HEATING: HVACMode.HEAT,
    OperationMode.FAN: HVACMode.FAN_ONLY,
    OperationMode.DRY: HVACMode.DRY,
    OperationMode.AUTO: HVACMode.HEAT_COOL,
}
HVAC_MODE_HASS_TO_LIB: Final[dict[HVACMode, OperationMode]] = {
    HVACMode.OFF: OperationMode.STOP,
    HVACMode.COOL: OperationMode.COOLING,
    HVACMode.HEAT: OperationMode.HEATING,
    HVACMode.FAN_ONLY: OperationMode.FAN,
    HVACMode.DRY: OperationMode.DRY,
    HVACMode.HEAT_COOL: OperationMode.AUTO,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add Airzone sensors from a config_entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AirzoneClimate(
            coordinator,
            entry,
            system_zone_id,
            zone_data,
        )
        for system_zone_id, zone_data in coordinator.data[AZD_ZONES].items()
    )


class AirzoneClimate(AirzoneZoneEntity, ClimateEntity):
    """Define an Airzone sensor."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        entry: ConfigEntry,
        system_zone_id: str,
        zone_data: dict,
    ) -> None:
        """Initialize Airzone climate entity."""
        super().__init__(coordinator, entry, system_zone_id, zone_data)

        self._attr_name = f"{zone_data[AZD_NAME]}"
        self._attr_unique_id = f"{self._attr_unique_id}_{system_zone_id}"
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_target_temperature_step = API_TEMPERATURE_STEP
        self._attr_max_temp = self.get_airzone_value(AZD_TEMP_MAX)
        self._attr_min_temp = self.get_airzone_value(AZD_TEMP_MIN)
        self._attr_temperature_unit = TEMP_UNIT_LIB_TO_HASS[
            self.get_airzone_value(AZD_TEMP_UNIT)
        ]
        self._attr_hvac_modes = [
            HVAC_MODE_LIB_TO_HASS[mode] for mode in self.get_airzone_value(AZD_MODES)
        ]
        self._async_update_attrs()

    async def _async_update_hvac_params(self, params: dict[str, Any]) -> None:
        """Send HVAC parameters to API."""
        _params = {
            API_SYSTEM_ID: self.system_id,
            API_ZONE_ID: self.zone_id,
            **params,
        }
        _LOGGER.debug("update_hvac_params=%s", _params)
        try:
            await self.coordinator.airzone.set_hvac_parameters(_params)
        except AirzoneError as error:
            raise HomeAssistantError(
                f"Failed to set zone {self.name}: {error}"
            ) from error
        else:
            self.coordinator.async_set_updated_data(self.coordinator.airzone.data())

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        params = {
            API_ON: 1,
        }
        await self._async_update_hvac_params(params)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        params = {
            API_ON: 0,
        }
        await self._async_update_hvac_params(params)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set hvac mode."""
        params = {}
        if hvac_mode == HVACMode.OFF:
            params[API_ON] = 0
        else:
            mode = HVAC_MODE_HASS_TO_LIB[hvac_mode]
            if mode != self.get_airzone_value(AZD_MODE):
                if self.get_airzone_value(AZD_MASTER):
                    params[API_MODE] = mode
                else:
                    raise HomeAssistantError(
                        f"Mode can't be changed on slave zone {self.name}"
                    )
            params[API_ON] = 1
        await self._async_update_hvac_params(params)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        params = {
            API_SET_POINT: kwargs.get(ATTR_TEMPERATURE),
        }
        await self._async_update_hvac_params(params)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update climate attributes."""
        self._attr_current_temperature = self.get_airzone_value(AZD_TEMP)
        self._attr_current_humidity = self.get_airzone_value(AZD_HUMIDITY)
        if self.get_airzone_value(AZD_ON):
            mode = self.get_airzone_value(AZD_MODE)
            self._attr_hvac_mode = HVAC_MODE_LIB_TO_HASS[mode]
            if self.get_airzone_value(AZD_DEMAND):
                self._attr_hvac_action = HVAC_ACTION_LIB_TO_HASS[mode]
            else:
                self._attr_hvac_action = HVACAction.IDLE
        else:
            self._attr_hvac_action = HVACAction.OFF
            self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = self.get_airzone_value(AZD_TEMP_SET)
