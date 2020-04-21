"""Initialization of ATAG One climate platform."""
from typing import List, Optional

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_BOOST,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.helpers.restore_state import RestoreEntity

from . import CLIMATE, DOMAIN, ENTITY_TYPES, AtagEntity

PRESET_SCHEDULE = "Auto"
PRESET_MANUAL = "Manual"
PRESET_EXTEND = "Extend"
SUPPORT_PRESET = [
    PRESET_MANUAL,
    PRESET_SCHEDULE,
    PRESET_EXTEND,
    PRESET_BOOST,
]
SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
HVAC_MODES = [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]


async def async_setup_entry(hass, entry, async_add_entities):
    """Load a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AtagThermostat(coordinator, ENTITY_TYPES[CLIMATE])])


class AtagThermostat(AtagEntity, ClimateDevice, RestoreEntity):
    """Atag climate device."""

    def __init__(self, coordinator, atagtype):
        """Initialize with fake on/off state."""
        self._on = None
        super().__init__(coordinator, atagtype)

    async def async_added_to_hass(self):
        """Register callbacks & state restore for fake "Off" mode."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._on = last_state.state != HVAC_MODE_OFF

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def hvac_mode(self) -> Optional[str]:
        """Return hvac operation ie. heat, cool mode."""
        if not self._on:
            return HVAC_MODE_OFF
        if self.coordinator.atag.hvac_mode in HVAC_MODES:
            return self.coordinator.atag.hvac_mode

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return HVAC_MODES

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation."""
        if self.coordinator.atag.cv_status:
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self.coordinator.atag.temperature

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return self.coordinator.atag.target_temperature

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., auto, manual, fireplace, extend, etc."""
        return self.coordinator.atag.hold_mode

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes."""
        return SUPPORT_PRESET

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if self._on and await self.coordinator.atag.set_temp(
            kwargs.get(ATTR_TEMPERATURE)
        ):
            await self.coordinator.async_refresh()

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        self._on = hvac_mode != HVAC_MODE_OFF
        if self._on:
            await self.coordinator.atag.set_hvac_mode(hvac_mode)
        await self.coordinator.async_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self._on:
            await self.coordinator.atag.set_hold_mode(preset_mode)
        await self.coordinator.async_refresh()
