"""Initialization of ATAG One climate platform."""
from typing import List, Optional

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.helpers.restore_state import RestoreEntity

from . import CLIMATE, DOMAIN, ENTITY_TYPES, AtagEntity


async def async_setup_platform(hass, _config, async_add_devices, _discovery_info=None):
    """Atag updated to use config entry."""
    pass


async def async_setup_entry(hass, entry, async_add_devices):
    """Load a config entry."""
    atag = hass.data[DOMAIN][entry.entry_id]
    async_add_devices([AtagThermostat(atag, ENTITY_TYPES[CLIMATE])])


class AtagThermostat(AtagEntity, ClimateDevice, RestoreEntity):
    """Atag climate device."""

    def __init__(self, atag, atagtype):
        """Initialize with fake on/off state."""
        super().__init__(atag, atagtype)
        self._on = None

    async def async_added_to_hass(self):
        """Register callbacks & state restore for fake "Off" mode."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._on = last_state.state != HVAC_MODE_OFF

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def hvac_mode(self) -> Optional[str]:
        """Return hvac operation ie. heat, cool mode."""
        if not self._on:
            return HVAC_MODE_OFF
        return self.atag.hvac_mode

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_HEAT, HVAC_MODE_AUTO, HVAC_MODE_OFF]

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation."""
        if self.atag.cv_status:
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self.atag.temperature

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return self.atag.target_temperature

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return DEFAULT_MAX_TEMP

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return DEFAULT_MIN_TEMP

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if self._on and await self.atag.set_temp(kwargs.get(ATTR_TEMPERATURE)):
            self.async_schedule_update_ha_state(True)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        self._on = hvac_mode != HVAC_MODE_OFF
        if self._on:
            await self.atag.set_hvac_mode(hvac_mode)
        self.async_schedule_update_ha_state()
