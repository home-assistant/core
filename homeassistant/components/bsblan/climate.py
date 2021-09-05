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
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_TEMPERATURE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_TARGET_TEMPERATURE, DATA_BSBLAN_CLIENT, DOMAIN

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

    _attr_supported_features = SUPPORT_FLAGS
    _attr_hvac_modes = HVAC_MODES
    _attr_preset_modes = PRESET_MODES

    def __init__(
        self,
        entry_id: str,
        bsblan: BSBLan,
        info: Info,
    ) -> None:
        """Initialize BSBLan climate device."""
        self._attr_available = True
        self._store_hvac_mode = None
        self.bsblan = bsblan
        self._attr_name = self._attr_unique_id = info.device_identification
        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(DOMAIN, info.device_identification)},
            ATTR_NAME: "BSBLan Device",
            ATTR_MANUFACTURER: "BSBLan",
            ATTR_MODEL: info.controller_variant,
        }

    async def async_set_preset_mode(self, preset_mode):
        """Set preset mode."""
        _LOGGER.debug("Setting preset mode to: %s", preset_mode)
        if preset_mode == PRESET_NONE:
            # restore previous hvac mode
            self._attr_hvac_mode = self._store_hvac_mode
        else:
            # Store hvac mode.
            self._store_hvac_mode = self._attr_hvac_mode
            await self.async_set_data(preset_mode=preset_mode)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode."""
        _LOGGER.debug("Setting HVAC mode to: %s", hvac_mode)
        # preset should be none when hvac mode is set
        self._attr_preset_mode = PRESET_NONE
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
            self._attr_available = False

    async def async_update(self) -> None:
        """Update BSBlan entity."""
        try:
            state: State = await self.bsblan.state()
        except BSBLanError:
            if self.available:
                _LOGGER.error("An error occurred while updating the BSBLan device")
            self._attr_available = False
            return

        self._attr_available = True

        self._attr_current_temperature = float(state.current_temperature.value)
        self._attr_target_temperature = float(state.target_temperature.value)

        # check if preset is active else get hvac mode
        _LOGGER.debug("state hvac/preset mode: %s", state.hvac_mode.value)
        if state.hvac_mode.value == "2":
            self._attr_preset_mode = PRESET_ECO
        else:
            self._attr_hvac_mode = BSBLAN_TO_HA_STATE[state.hvac_mode.value]
            self._attr_preset_mode = PRESET_NONE

        self._attr_temperature_unit = (
            TEMP_CELSIUS
            if state.current_temperature.unit == "&deg;C"
            else TEMP_FAHRENHEIT
        )
