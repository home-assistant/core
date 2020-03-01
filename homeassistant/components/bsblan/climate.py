"""BSBLAN platform to control a compatible Climate Device."""
from datetime import timedelta
import logging
from typing import Any, Callable, Dict, List, Optional

from bsblan import BSBLan, BSBLanError, Info, State

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
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
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_INSIDE_TEMPERATURE,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_OUTSIDE_TEMPERATURE,
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
    PRESET_ECO: "2",
    HVAC_MODE_HEAT: "3",
    HVAC_MODE_OFF: "0",
    # HVAC_MODE_COOL: "cool",  # not yet implemented
}

HA_ATTR_TO_BSBLAN = {
    ATTR_HVAC_MODE: "hvac_modes",
    ATTR_INSIDE_TEMPERATURE: "8740",  # not yet implemented
    ATTR_OUTSIDE_TEMPERATURE: "8700",  # not yet implemented
    ATTR_TARGET_TEMPERATURE: "target_temperature",
}

HA_PRESET_TO_BSBLAN = {
    PRESET_ECO: "2",
}

BSBLAN_TO_HA_STATE = {
    "1": HVAC_MODE_AUTO,
    "2": PRESET_ECO,
    "3": HVAC_MODE_HEAT,
    "0": HVAC_MODE_OFF,
}
# protection=0,auto=1,reduced=2,comfort=3


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up BSBLan device based on a config entry."""
    bsblan: BSBLan = hass.data[DOMAIN][entry.entry_id][DATA_BSBLAN_CLIENT]
    info = await bsblan.info()
    async_add_entities([BSBLanClimate(entry.entry_id, bsblan, info)], True)


class BSBLanClimate(ClimateDevice):
    """Defines a BSBLan climate device."""

    def __init__(
        self, entry_id: str, bsblan: BSBLan, info: Info,
    ):
        """Initialize BSBLan climate device."""
        self._current_temperature: Optional[float] = None
        self._available = True
        self._current_hvac_mode: Optional[int] = None
        self._target_temperature: Optional[float] = None
        self._info: Info = info
        self.bsblan = bsblan
        self._hvac_modes = HVAC_MODES
        self._preset_modes = PRESET_MODES
        self._temperature_unit = None
        self._hvac_mode = None
        self._preset_mode = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        if not self._info.device_identification:
            return self._info.controller_family
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
        return self._current_hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return self._hvac_modes

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def preset_modes(self):
        """List of available preset modes."""
        return self._preset_modes

    @property
    def preset_mode(self):
        """Return the preset_mode."""
        if self._current_hvac_mode == 2:
            return PRESET_ECO
        return PRESET_NONE

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode."""
        _LOGGER.info("Setting HVAC mode to: %s", hvac_mode)
        await self.async_set_data(hvac_mode=hvac_mode)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        await self.async_set_data(**kwargs)

    async def async_set_data(self, **kwargs: Any) -> None:
        """Set device settings using BSBLan."""
        data = {}

        if ATTR_TEMPERATURE in kwargs:
            data[ATTR_TARGET_TEMPERATURE] = kwargs[ATTR_TEMPERATURE]
            _LOGGER.info("data = %s", data)

        if ATTR_HVAC_MODE in kwargs:
            data[ATTR_HVAC_MODE] = HA_STATE_TO_BSBLAN[kwargs[ATTR_HVAC_MODE]]
            _LOGGER.info("data hvac mode = %s", data)

        try:
            await self.bsblan.thermostat(**data)
        except BSBLanError:
            _LOGGER.error("An error occurred while updating the BSBLan Device")
            self._available = False

    async def async_update(self) -> None:
        """Update BSBlan entity."""
        try:
            state: State = await self.bsblan.state()
        except BSBLanError:
            if self._available:
                _LOGGER.error("An error occurred while updating the BSBLan device.")
            self._available = False
            return

        self._available = True

        self._current_temperature = float(state.current_temperature)
        self._target_temperature = float(state.target_temperature)

        self._current_hvac_mode = BSBLAN_TO_HA_STATE[state.current_hvac_mode]

        self._temperature_unit = state.temperature_unit
        # self._current_hvac_operation = state.current_hvac_operation
        # self._current_heatpump_mode = state.current_heatpump_mode

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this BSBLan device."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._info.device_identification)},
            ATTR_NAME: self._info.controller_family,
            ATTR_MANUFACTURER: "BSBLan",
            ATTR_MODEL: self._info.controller_variant,
        }
