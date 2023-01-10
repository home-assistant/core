"""Support for Seitron thermostats IoT climate devices."""
from __future__ import annotations

import logging
from typing import Any

from pyseitron.seitron_thermostat import SeitronThermostat

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN  # seitron

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the seitron climate entities from a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    # coordinator.data is a SeitronGateway
    async_add_entities(
        SeitronClimate(coordinator, thermostat)
        for thermostat in coordinator.data.devices
    )


class SeitronClimate(CoordinatorEntity, ClimateEntity):
    """A Seitron IoT thermostat climate entity."""

    _attr_precision = PRECISION_TENTHS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.AUTO, HVACMode.COOL, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_max_temp = 50
    _attr_min_temp = -10
    _attr_target_temperature_high = 40
    _attr_target_temperature_low = 5
    _attr_target_temperature_step = 0.1
    _attr_should_poll = True
    _attr_icon = "mdi:thermostat-box"

    def __init__(self, coordinator, thermostat: SeitronThermostat) -> None:
        """Initialize an Seitron climate device."""
        super().__init__(coordinator)
        self._thermostat = thermostat
        self._attr_has_entity_name = True
        self._attr_unique_id = thermostat.gmac
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, thermostat.gmac)},
            manufacturer=thermostat.manufacturer,
            model=thermostat.model,
            name=thermostat.name,
            sw_version=thermostat.fw_ver,
        )
        _LOGGER.info("Climate: ctored %s %s", thermostat.gmac, thermostat.name)

    @property
    def temperature_unit(self) -> str:
        """Return the temperature unit."""
        if self._thermostat.farhenheit:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._thermostat.temp_curr

    @property
    def target_temperature(self) -> float | None:
        """Return the setpoint."""
        _LOGGER.info("Climate: getting target")
        return self._thermostat.temp_target

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. auto, heat mode."""
        if self._thermostat.mode == "COOL":
            return HVACMode.COOL
        if self._thermostat.mode == "HEAT":
            return HVACMode.HEAT
        if self._thermostat.mode == "AUTO":
            return HVACMode.AUTO
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        """Return boiler status."""
        if self._thermostat.hvac_action == "COOLING":
            return HVACAction.COOLING
        if self._thermostat.hvac_action == "HEATING":
            return HVACAction.HEATING
        if self._thermostat.hvac_action == "OFF":
            return HVACAction.OFF
        return HVACAction.IDLE

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""

        if hvac_mode == HVACMode.COOL:
            await self.coordinator.data.set_hvac_mode(self._thermostat.gmac, "COOL")
        elif hvac_mode == HVACMode.HEAT:
            await self.coordinator.data.set_hvac_mode(self._thermostat.gmac, "HEAT")
        elif hvac_mode == HVACMode.AUTO:
            await self.coordinator.data.set_hvac_mode(self._thermostat.gmac, "AUTO")
        else:
            await self.coordinator.data.set_hvac_mode(self._thermostat.gmac, "OFF")

        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp: float = kwargs[ATTR_TEMPERATURE]
        await self.coordinator.data.set_temperature(self._thermostat.gmac, temp)
        await self.coordinator.async_request_refresh()
