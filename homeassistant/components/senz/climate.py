"""nVent RAYCHEM SENZ climate platform."""
from __future__ import annotations

from typing import Any

from aiosenz import MODE_AUTO, Thermostat

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SENZDataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SENZ climate entities from a config entry."""
    coordinator: SENZDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SENZClimate(thermostat, coordinator) for thermostat in coordinator.data.values()
    )


class SENZClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a SENZ climate entity."""

    _attr_temperature_unit = TEMP_CELSIUS
    _attr_precision = PRECISION_TENTHS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.AUTO]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_max_temp = 35
    _attr_min_temp = 5

    def __init__(
        self,
        thermostat: Thermostat,
        coordinator: SENZDataUpdateCoordinator,
    ) -> None:
        """Init SENZ climate."""
        super().__init__(coordinator)
        self._thermostat = thermostat
        self._attr_name = thermostat.name
        self._attr_unique_id = thermostat.serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, thermostat.serial_number)},
            manufacturer="nVent Raychem",
            model="SENZ WIFI",
            name=thermostat.name,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._thermostat = self.coordinator.data[self._thermostat.serial_number]
        self.async_write_ha_state()

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._thermostat.current_temperatue

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self._thermostat.setpoint_temperature

    @property
    def available(self) -> bool:
        """Return True if the thermostat is available."""
        return self._thermostat.online

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. auto, heat mode."""
        if self._thermostat.mode == MODE_AUTO:
            return HVACMode.AUTO
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        """Return current hvac action."""
        return HVACAction.HEATING if self._thermostat.is_heating else HVACAction.IDLE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.AUTO:
            await self._thermostat.auto()
        else:
            await self._thermostat.manual()
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp: float = kwargs[ATTR_TEMPERATURE]
        await self._thermostat.manual(temp)
        await self.coordinator.async_request_refresh()
