"""BSBLAN platform to control a compatible Climate Device."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from bsblan import BSBLan, BSBLanError, Info, State

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_ECO,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    ATTR_TEMPERATURE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_TARGET_TEMPERATURE,
    DATA_BSBLAN_CLIENT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=20)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

HVAC_MODES = [
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
]

PRESET_MODES = [
    PRESET_ECO,
    PRESET_NONE,
]

HA_STATE_TO_BSBLAN = {
    HVAC_MODE_AUTO: "1",
    HVAC_MODE_HEAT: "3",
    HVAC_MODE_OFF: "0",
}

BSBLAN_TO_HA_STATE = {value: key for key, value in HA_STATE_TO_BSBLAN.items()}

HA_PRESET_TO_BSBLAN = {
    PRESET_ECO: "2",
}

BSBLAN_TO_HA_PRESET = {
    2: PRESET_ECO,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BSBLan device based on a config entry."""
    bsblan: BSBLan = hass.data[DOMAIN][entry.entry_id][DATA_BSBLAN_CLIENT]
    info = await bsblan.info()
    async_add_entities([BSBLanClimate(entry.entry_id, bsblan, info)], True)


class BSBLanClimate(ClimateEntity):
    """Defines a BSBLan climate device."""

    def __init__(
        self,
        entry_id: str,
        bsblan: BSBLan,
        info: Info,
    ):
        """Initialize BSBLan climate device."""
        self._current_temperature: float | None = None
        self._available = True
        self._hvac_mode: str | None = None
        self._target_temperature: float | None = None
        self._temperature_unit = None
        self._preset_mode = None
        self._store_hvac_mode = None
        self._info: Info = info
        self.bsblan = bsblan

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._info.device_identification

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return self._info.device_identification

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement which this thermostat uses."""
        if self._temperature_unit == "&deg;C":
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_FLAGS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def hvac_mode(self):
        """Return the current operation mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return HVAC_MODES

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def preset_modes(self):
        """List of available preset modes."""
        return PRESET_MODES

    @property
    def preset_mode(self):
        """Return the preset_mode."""
        return self._preset_mode

    async def async_set_preset_mode(self, preset_mode):
        """Set preset mode."""
        _LOGGER.debug("Setting preset mode to: %s", preset_mode)
        if preset_mode == PRESET_NONE:
            # restore previous hvac mode
            self._hvac_mode = self._store_hvac_mode
        else:
            # Store hvac mode.
            self._store_hvac_mode = self._hvac_mode
            await self.async_set_data(preset_mode=preset_mode)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode."""
        _LOGGER.debug("Setting HVAC mode to: %s", hvac_mode)
        # preset should be none when hvac mode is set
        self._preset_mode = PRESET_NONE
        await self.async_set_data(hvac_mode=hvac_mode)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        await self.async_set_data(**kwargs)

    async def async_set_data(self, **kwargs: Any) -> None:
        """Set device settings using BSBLan."""
        data = {}

        if ATTR_TEMPERATURE in kwargs:
            data[ATTR_TARGET_TEMPERATURE] = kwargs[ATTR_TEMPERATURE]
            _LOGGER.debug("Set temperature data = %s", data)

        if ATTR_HVAC_MODE in kwargs:
            data[ATTR_HVAC_MODE] = HA_STATE_TO_BSBLAN[kwargs[ATTR_HVAC_MODE]]
            _LOGGER.debug("Set hvac mode data = %s", data)

        if ATTR_PRESET_MODE in kwargs:
            # for now we set the preset as hvac_mode as the api expect this
            data[ATTR_HVAC_MODE] = HA_PRESET_TO_BSBLAN[kwargs[ATTR_PRESET_MODE]]

        try:
            await self.bsblan.thermostat(**data)
        except BSBLanError:
            _LOGGER.error("An error occurred while updating the BSBLan device")
            self._available = False

    async def async_update(self) -> None:
        """Update BSBlan entity."""
        try:
            state: State = await self.bsblan.state()
        except BSBLanError:
            if self._available:
                _LOGGER.error("An error occurred while updating the BSBLan device")
            self._available = False
            return

        self._available = True

        self._current_temperature = float(state.current_temperature.value)
        self._target_temperature = float(state.target_temperature.value)

        # check if preset is active else get hvac mode
        _LOGGER.debug("state hvac/preset mode: %s", state.hvac_mode.value)
        if state.hvac_mode.value == "2":
            self._preset_mode = PRESET_ECO
        else:
            self._hvac_mode = BSBLAN_TO_HA_STATE[state.hvac_mode.value]
            self._preset_mode = PRESET_NONE

        self._temperature_unit = state.current_temperature.unit

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this BSBLan device."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._info.device_identification)},
            ATTR_NAME: "BSBLan Device",
            ATTR_MANUFACTURER: "BSBLan",
            ATTR_MODEL: self._info.controller_variant,
        }
