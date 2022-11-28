"""CoolMasterNet platform to control of CoolMasterNet Climate Devices."""
import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SUPPORTED_MODES, DATA_COORDINATOR, DATA_INFO, DOMAIN

CM_TO_HA_STATE = {
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "auto": HVACMode.HEAT_COOL,
    "dry": HVACMode.DRY,
    "fan": HVACMode.FAN_ONLY,
}

HA_STATE_TO_CM = {value: key for key, value in CM_TO_HA_STATE.items()}

FAN_MODES = ["low", "med", "high", "auto"]

_LOGGER = logging.getLogger(__name__)


def _build_entity(coordinator, unit_id, unit, supported_modes, info):
    _LOGGER.debug("Found device %s", unit_id)
    return CoolmasterClimate(coordinator, unit_id, unit, supported_modes, info)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up the CoolMasterNet climate platform."""
    supported_modes = config_entry.data.get(CONF_SUPPORTED_MODES)
    info = hass.data[DOMAIN][config_entry.entry_id][DATA_INFO]

    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    all_devices = [
        _build_entity(coordinator, unit_id, unit, supported_modes, info)
        for (unit_id, unit) in coordinator.data.items()
    ]

    async_add_devices(all_devices)


class CoolmasterClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a coolmaster climate device."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )

    def __init__(self, coordinator, unit_id, unit, supported_modes, info):
        """Initialize the climate device."""
        super().__init__(coordinator)
        self._unit_id = unit_id
        self._unit = unit
        self._hvac_modes = supported_modes
        self._info = info

    @callback
    def _handle_coordinator_update(self):
        self._unit = self.coordinator.data[self._unit_id]
        super()._handle_coordinator_update()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer="CoolAutomation",
            model="CoolMasterNet",
            name=self.name,
            sw_version=self._info["version"],
        )

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._unit_id

    @property
    def name(self):
        """Return the name of the climate device."""
        return self.unique_id

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        if self._unit.temperature_unit == "celsius":
            return TEMP_CELSIUS

        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._unit.temperature

    @property
    def target_temperature(self):
        """Return the temperature we are trying to reach."""
        return self._unit.thermostat

    @property
    def hvac_mode(self):
        """Return hvac target hvac state."""
        mode = self._unit.mode
        if not self._unit.is_on:
            return HVACMode.OFF

        return CM_TO_HA_STATE[mode]

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return self._hvac_modes

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._unit.fan_speed

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return FAN_MODES

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            _LOGGER.debug("Setting temp of %s to %s", self.unique_id, str(temp))
            self._unit = await self._unit.set_thermostat(temp)
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        _LOGGER.debug("Setting fan mode of %s to %s", self.unique_id, fan_mode)
        self._unit = await self._unit.set_fan_speed(fan_mode)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        _LOGGER.debug("Setting operation mode of %s to %s", self.unique_id, hvac_mode)

        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            self._unit = await self._unit.set_mode(HA_STATE_TO_CM[hvac_mode])
            await self.async_turn_on()

    async def async_turn_on(self) -> None:
        """Turn on."""
        _LOGGER.debug("Turning %s on", self.unique_id)
        self._unit = await self._unit.turn_on()
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn off."""
        _LOGGER.debug("Turning %s off", self.unique_id)
        self._unit = await self._unit.turn_off()
        self.async_write_ha_state()
