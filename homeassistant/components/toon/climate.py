"""Support for Toon thermostat."""

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_HEAT,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_HOME,
    PRESET_SLEEP,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.helpers.typing import HomeAssistantType

from . import ToonData, ToonDisplayDeviceEntity
from .const import (
    DATA_TOON,
    DATA_TOON_CLIENT,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
SUPPORT_PRESET = [PRESET_AWAY, PRESET_COMFORT, PRESET_HOME, PRESET_SLEEP]


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up a Toon binary sensors based on a config entry."""
    toon_client = hass.data[DATA_TOON_CLIENT][entry.entry_id]
    toon_data = hass.data[DATA_TOON][entry.entry_id]
    async_add_entities([ToonThermostatDevice(toon_client, toon_data)], True)


class ToonThermostatDevice(ToonDisplayDeviceEntity, ClimateEntity):
    """Representation of a Toon climate device."""

    def __init__(self, toon_client, toon_data: ToonData) -> None:
        """Initialize the Toon climate device."""
        self._client = toon_client

        self._current_temperature = None
        self._target_temperature = None
        self._heating = False
        self._next_target_temperature = None
        self._preset = None

        self._heating_type = None

        super().__init__(toon_data, "Toon Thermostat", "mdi:thermostat")

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this thermostat."""
        return "_".join([DOMAIN, self.toon.agreement.id, "climate"])

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_HEAT]

    @property
    def hvac_action(self) -> Optional[str]:
        """Return the current running hvac operation."""
        if self._heating:
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        if self._preset is not None:
            return self._preset.lower()
        return None

    @property
    def preset_modes(self) -> List[str]:
        """Return a list of available preset modes."""
        return SUPPORT_PRESET

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return DEFAULT_MAX_TEMP

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the current state of the burner."""
        return {"heating_type": self._heating_type}

    def set_temperature(self, **kwargs) -> None:
        """Change the setpoint of the thermostat."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        self._client.thermostat = self._target_temperature = temperature
        self.schedule_update_ha_state()

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        self._client.thermostat_state = self._preset = preset_mode
        self.schedule_update_ha_state()

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""

    def update(self) -> None:
        """Update local state."""
        if self.toon.thermostat_state is None:
            self._preset = None
        else:
            self._preset = self.toon.thermostat_state.name

        self._current_temperature = self.toon.temperature
        self._target_temperature = self.toon.thermostat
        self._heating_type = self.toon.agreement.heating_type
        self._heating = self.toon.thermostat_info.burner_info == 1
