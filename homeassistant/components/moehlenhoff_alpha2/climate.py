"""Support for Alpha2 room control unit via Alpha2 base."""
import logging

import aiohttp

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import Alpha2BaseCoordinator
from .const import DOMAIN, PRESET_AUTO, PRESET_DAY, PRESET_NIGHT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Alpha2Climate entities from a config_entry."""

    coordinator: Alpha2BaseCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        Alpha2Climate(coordinator, heatarea_id) for heatarea_id in coordinator.data
    )


# https://developers.home-assistant.io/docs/core/entity/climate/
class Alpha2Climate(CoordinatorEntity, ClimateEntity):
    """Alpha2 ClimateEntity."""

    target_temperature_step = 0.2

    _attr_should_poll = False
    _attr_supported_features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
    _attr_hvac_modes = [HVAC_MODE_HEAT, HVAC_MODE_COOL]
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_preset_modes = [PRESET_AUTO, PRESET_DAY, PRESET_NIGHT]

    def __init__(self, coordinator: Alpha2BaseCoordinator, heatarea_id: str):
        """Initialize Alpha2 ClimateEntity."""
        super().__init__(coordinator)
        # Set the right type for mypy
        self.coordinator: Alpha2BaseCoordinator = self.coordinator
        self.heatarea_id = heatarea_id

    @property
    def name(self) -> str:
        """Return the name of the climate device."""
        return self.coordinator.data[self.heatarea_id]["HEATAREA_NAME"]

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return float(self.coordinator.data[self.heatarea_id].get("T_TARGET_MIN", 0.0))

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return float(self.coordinator.data[self.heatarea_id].get("T_TARGET_MAX", 30.0))

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return float(self.coordinator.data[self.heatarea_id].get("T_ACTUAL", 0.0))

    @property
    def hvac_mode(self) -> str:
        """Return current hvac mode."""
        if self.coordinator.get_cooling():
            return HVAC_MODE_COOL
        return HVAC_MODE_HEAT

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        await self.coordinator.async_set_cooling(hvac_mode == HVAC_MODE_COOL)

    @property
    def hvac_action(self) -> str:
        """Return the current running hvac operation."""
        if not self.coordinator.data[self.heatarea_id]["_HEATCTRL_STATE"]:
            return CURRENT_HVAC_IDLE
        if self.coordinator.get_cooling():
            return CURRENT_HVAC_COOL
        return CURRENT_HVAC_HEAT

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return float(self.coordinator.data[self.heatarea_id].get("T_TARGET", 0.0))

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperatures."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is None:
            return

        try:
            await self.coordinator.async_set_target_temperature(
                self.coordinator.data[self.heatarea_id]["ID"], target_temperature
            )
            self.coordinator.data[self.heatarea_id]["T_TARGET"] = target_temperature
        except Exception as update_err:  # pylint: disable=broad-except
            _LOGGER.error("Setting target temperature failed: %s", update_err)

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        if self.coordinator.data[self.heatarea_id]["HEATAREA_MODE"] == 1:
            return PRESET_DAY
        if self.coordinator.data[self.heatarea_id]["HEATAREA_MODE"] == 2:
            return PRESET_NIGHT
        return PRESET_AUTO

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new operation mode."""
        heatarea_mode = 0
        if preset_mode == PRESET_DAY:
            heatarea_mode = 1
        elif preset_mode == PRESET_NIGHT:
            heatarea_mode = 2

        try:
            await self.coordinator.async_set_heatarea_mode(
                self.coordinator.data[self.heatarea_id]["ID"], heatarea_mode
            )
        except aiohttp.web.HTTPRequestTimeout as http_err:
            _LOGGER.error(
                "Failed to set target temperature, base is unreachable: %s", http_err
            )
        except Exception as update_err:  # pylint: disable=broad-except
            _LOGGER.error("Failed to set target temperature: %s", update_err)
        else:
            self.coordinator.data[self.heatarea_id]["HEATAREA_MODE"] = heatarea_mode
            if heatarea_mode == 1:
                if self.coordinator.get_cooling():
                    self.coordinator.data[self.heatarea_id][
                        "T_TARGET"
                    ] = self.coordinator.data[self.heatarea_id]["T_COOL_DAY"]
                else:
                    self.coordinator.data[self.heatarea_id][
                        "T_TARGET"
                    ] = self.coordinator.data[self.heatarea_id]["T_HEAT_DAY"]
            elif heatarea_mode == 2:
                if self.coordinator.get_cooling():
                    self.coordinator.data[self.heatarea_id][
                        "T_TARGET"
                    ] = self.coordinator.data[self.heatarea_id]["T_COOL_NIGHT"]
                else:
                    self.coordinator.data[self.heatarea_id][
                        "T_TARGET"
                    ] = self.coordinator.data[self.heatarea_id]["T_HEAT_NIGHT"]

    @property
    def extra_state_attributes(self):
        """Return the optional state attributes."""
        data = super().extra_state_attributes or {}
        data["islocked"] = self.coordinator.data[self.heatarea_id].get(
            "ISLOCKED", False
        )
        data["lock_available"] = self.coordinator.data[self.heatarea_id].get(
            "LOCK_AVAILABLE", False
        )
        data["block_hc"] = self.coordinator.data[self.heatarea_id].get(
            "BLOCK_HC", False
        )
        return data
