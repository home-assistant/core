"""Support for the Airzone climate."""
from __future__ import annotations

import logging

from aioairzone.const import (
    API_MODE,
    API_ON,
    API_SET_POINT,
    API_SYSTEM_ID,
    API_ZONE_ID,
    AZD_DEMAND,
    AZD_HUMIDITY,
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
from aiohttp.client_exceptions import ClientConnectorError

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirzoneEntity
from .const import (
    API_TEMPERATURE_STEP,
    DOMAIN,
    HVAC_ACTION_LIB_TO_HASS,
    HVAC_MODE_HASS_TO_LIB,
    HVAC_MODE_LIB_TO_HASS,
    TEMP_UNIT_LIB_TO_HASS,
)
from .coordinator import AirzoneUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


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


class AirzoneClimate(AirzoneEntity, ClimateEntity):
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
        self._attr_unique_id = f"{entry.entry_id}_{system_zone_id}"
        self._attr_supported_features = SUPPORT_TARGET_TEMPERATURE
        self._attr_target_temperature_step = API_TEMPERATURE_STEP
        self._attr_max_temp = self.get_zone_value(AZD_TEMP_MAX)
        self._attr_min_temp = self.get_zone_value(AZD_TEMP_MIN)
        self._attr_temperature_unit = TEMP_UNIT_LIB_TO_HASS[
            self.get_zone_value(AZD_TEMP_UNIT)
        ]
        self._attr_hvac_modes = [
            HVAC_MODE_LIB_TO_HASS[mode]
            for mode in self.get_zone_value(AZD_MODES)
            or [self.get_zone_value(AZD_MODE)]
        ]
        if HVAC_MODE_OFF not in self._attr_hvac_modes:
            self._attr_hvac_modes.append(HVAC_MODE_OFF)
        self._async_update_attrs()        

    async def async_update_hvac_params(self, params) -> None:
        """Send HVAC parameters to API."""
        try:
            await self.coordinator.airzone.put_hvac(params)
        except (AirzoneError, ClientConnectorError) as error:
            raise HomeAssistantError(f"Failed to set zone {self.name}: {error}") from error
        else:
            self.coordinator.async_set_updated_data(self.coordinator.airzone.data())

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set hvac mode."""
        params = {
            API_SYSTEM_ID: self.system_id,
            API_ZONE_ID: self.zone_id,
        }
        if hvac_mode == HVAC_MODE_OFF:
            params[API_ON] = 0
        else:
            if self.get_zone_value(AZD_MODES):
                mode = HVAC_MODE_HASS_TO_LIB[hvac_mode]
                if mode != self.get_zone_value(AZD_MODE):
                    params[API_MODE] = mode
            params[API_ON] = 1
        _LOGGER.debug("Set hvac_mode=%s params=%s", hvac_mode, params)
        await self._async_update_hvac_params(params)

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        params = {
            API_SYSTEM_ID: self.system_id,
            API_ZONE_ID: self.zone_id,
            API_SET_POINT: temp,
        }
        _LOGGER.debug("Set temp=%s params=%s", temp, params)
        await self._async_update_hvac_params(params)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        self._attr_current_temperature = self.get_zone_value(AZD_TEMP)
        self._attr_current_humidity = self.get_zone_value(AZD_HUMIDITY)
        if self.get_zone_value(AZD_ON):
            if self.get_zone_value(AZD_DEMAND):
                self._attr_hvac_action = HVAC_ACTION_LIB_TO_HASS[
                    self.get_zone_value(AZD_MODE)
                ]
            else:
                self._attr_hvac_action = CURRENT_HVAC_IDLE
        else:
            self._attr_hvac_action = CURRENT_HVAC_OFF
        if self.get_zone_value(AZD_ON):
            self._attr_hvac_mode = HVAC_MODE_LIB_TO_HASS[self.get_zone_value(AZD_MODE)]
        else:
            self._attr_hvac_mode = HVAC_MODE_OFF
        self._attr_target_temperature = self.get_zone_value(AZD_TEMP_SET)
