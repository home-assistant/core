"""Support for Broadlink-based Hysen thermostats."""
from typing import Any

from homeassistant.components.climate import (
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BroadlinkEntity

FACTORY_DEFAULT_MIN_TEMP = 5.0
FACTORY_DEFAULT_MAX_TEMP = 35.0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Broadlink light."""
    device = hass.data[DOMAIN].devices[config_entry.entry_id]
    thermostats = []

    if device.api.type == "HYS":
        thermostats.append(BroadlinkClimateEntity(device))

    async_add_entities(thermostats)


class BroadlinkClimateEntity(BroadlinkEntity, ClimateEntity):
    """Representation of a Broadlink entity."""

    _attr_has_entity_name = True
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT]
    _attr_name = None
    _attr_preset_modes = [PRESET_NONE]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = DOMAIN

    def __init__(self, device):
        """Initialize entity representing the device."""
        super().__init__(device)
        self._attr_unique_id = device.unique_id

        data = self._coordinator.data

        self._update_state(data)

    def _update_state(self, data):
        """Update the local state based on full_status of the device."""
        self._active = data["active"]
        self._auto_mode = data["auto_mode"]
        self._dayofweek = data["dayofweek"]
        self._dif = data["dif"]
        self._external_temp = data["external_temp"]
        self._fre = data["fre"]
        self._hour = data["hour"]
        self._loop_mode = data["loop_mode"]
        self._min = data["min"]
        self._osv = data["osv"]
        self._power = data["power"]
        self._poweron = data["poweron"]
        self._remote_lock = data["remote_lock"]
        self._room_temp = data["room_temp"]
        self._room_temp_adj = data["room_temp_adj"]
        self._sec = data["sec"]
        self._sensor = data["sensor"]
        self._svh = data["svh"]
        self._svl = data["svl"]
        self._temp_manual = data["temp_manual"]
        self._thermostat_temp = data["thermostat_temp"]
        self._unknown = data["unknown"]

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Current HVAC mode."""
        if self._power == 0:
            return HVACMode.OFF
        if self._auto_mode == 1:
            return HVACMode.AUTO
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        """Current HVAC action."""
        if self._power == 0:
            return HVACAction.OFF
        if self._active == 1:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def icon(self) -> str | None:
        """Icon representing current HVACAction."""
        match self.hvac_action:
            case HVACAction.OFF:
                return "mdi:radiator-off"
            case HVACAction.HEATING:
                return "mdi:radiator"
            case HVACAction.IDLE:
                return "mdi:radiator-disabled"
            case _:
                # shouldn't really happen?
                return "mdi:radiator"

    @property
    def preset_mode(self) -> str | None:
        """No presets currently supported."""
        return PRESET_NONE

    @property
    def current_temperature(self) -> float | None:
        """Current room temperature."""
        return self._room_temp

    @property
    def target_temperature(self) -> float | None:
        """Target temperature."""
        return self._thermostat_temp

    @property
    def min_temp(self) -> float:
        """Minimum temperature configured in the thermostat."""
        return self._svl

    @property
    def max_temp(self) -> float:
        """Maximum temperature configured in the thermostat."""
        return self._svh

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        await self._device.async_request(self._device.api.set_temp, temperature)
        self.async_schedule_update_ha_state(force_refresh=True)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode - off, heat or auto."""
        if hvac_mode == HVACMode.OFF:
            await self._device.async_request(self._device.api.set_power, power=0)
        else:
            await self._device.async_request(self._device.api.set_power, power=1)
            if hvac_mode == HVACMode.HEAT:
                await self._device.async_request(
                    self._device.api.set_mode, auto_mode=0, loop_mode=0
                )
            elif hvac_mode == HVACMode.AUTO:
                await self._device.async_request(
                    self._device.api.set_mode, auto_mode=1, loop_mode=0
                )
        self.async_schedule_update_ha_state(force_refresh=True)
