"""Support for Spider thermostats."""
from __future__ import annotations

from typing import Any

from spiderpy.devices.thermostat import SpiderThermostat
from spiderpy.spiderapi import SpiderApi

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

HA_STATE_TO_SPIDER = {
    HVAC_MODE_COOL: "Cool",
    HVAC_MODE_HEAT: "Heat",
    HVAC_MODE_OFF: "Idle",
}

SPIDER_STATE_TO_HA = {value: key for key, value in HA_STATE_TO_SPIDER.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize a Spider thermostat."""
    api = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            Thermostat(api, entity)
            for entity in await hass.async_add_executor_job(api.get_thermostats)
        ]
    )


class Thermostat(ClimateEntity):
    """Representation of a thermostat."""

    def __init__(self, api: SpiderApi, thermostat: SpiderThermostat) -> None:
        """Initialize the thermostat."""
        self.api: SpiderApi = api
        self.thermostat: SpiderThermostat = thermostat
        self.support_fan: list[str] = thermostat.available_fan_speed_modes
        self.support_hvac: list[str] = []
        for operation_mode in thermostat.available_operation_modes:
            if operation_mode in SPIDER_STATE_TO_HA:
                self.support_hvac.append(SPIDER_STATE_TO_HA[operation_mode])

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.thermostat.id)},
            manufacturer=self.thermostat.manufacturer,
            model=self.thermostat.model,
            name=self.thermostat.name,
        )

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        if self.thermostat.has_fan_speed_mode:
            return SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def unique_id(self) -> str:
        """Return the id of the thermostat, if any."""
        return self.thermostat.id

    @property
    def name(self) -> str:
        """Return the name of the thermostat, if any."""
        return self.thermostat.name

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self.thermostat.current_temperature

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self.thermostat.target_temperature

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return self.thermostat.temperature_steps

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self.thermostat.minimum_temperature

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self.thermostat.maximum_temperature

    @property
    def hvac_mode(self) -> str:
        """Return current operation ie. heat, cool, idle."""
        return SPIDER_STATE_TO_HA[self.thermostat.current_operation_mode]

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available operation modes."""
        return self.support_hvac

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        self.api.set_temperature(self.thermostat, temperature)

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target operation mode."""
        self.api.set_operation_mode(
            self.thermostat, str(HA_STATE_TO_SPIDER.get(hvac_mode))
        )

    @property
    def fan_mode(self) -> str:
        """Return the fan setting."""
        return self.thermostat.current_fan_speed_mode

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        self.api.set_fan_speed(self.thermostat, fan_mode)

    @property
    def fan_modes(self) -> list[str] | None:
        """List of available fan modes."""
        return self.support_fan

    def update(self) -> None:
        """Get the latest data."""
        thermostat = self.api.get_thermostat(self.unique_id)
        if thermostat is not None:
            self.thermostat = thermostat
