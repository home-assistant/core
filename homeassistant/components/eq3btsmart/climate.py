"""Support for eQ-3 Bluetooth Smart thermostats."""
from __future__ import annotations

import logging
from typing import Any

import eq3bt as eq3  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_DEVICES,
    CONF_MAC,
    PRECISION_HALVES,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import PRESET_CLOSED, PRESET_NO_HOLD, PRESET_OPEN, PRESET_PERMANENT_HOLD

_LOGGER = logging.getLogger(__name__)

STATE_BOOST = "boost"

ATTR_STATE_WINDOW_OPEN = "window_open"
ATTR_STATE_VALVE = "valve"
ATTR_STATE_LOCKED = "is_locked"
ATTR_STATE_LOW_BAT = "low_battery"
ATTR_STATE_AWAY_END = "away_end"

EQ_TO_HA_HVAC = {
    eq3.Mode.Open: HVACMode.HEAT,
    eq3.Mode.Closed: HVACMode.OFF,
    eq3.Mode.Auto: HVACMode.AUTO,
    eq3.Mode.Manual: HVACMode.HEAT,
    eq3.Mode.Boost: HVACMode.AUTO,
    eq3.Mode.Away: HVACMode.HEAT,
}

HA_TO_EQ_HVAC = {
    HVACMode.HEAT: eq3.Mode.Manual,
    HVACMode.OFF: eq3.Mode.Closed,
    HVACMode.AUTO: eq3.Mode.Auto,
}

EQ_TO_HA_PRESET = {
    eq3.Mode.Boost: PRESET_BOOST,
    eq3.Mode.Away: PRESET_AWAY,
    eq3.Mode.Manual: PRESET_PERMANENT_HOLD,
    eq3.Mode.Auto: PRESET_NO_HOLD,
    eq3.Mode.Open: PRESET_OPEN,
    eq3.Mode.Closed: PRESET_CLOSED,
}

HA_TO_EQ_PRESET = {
    PRESET_BOOST: eq3.Mode.Boost,
    PRESET_AWAY: eq3.Mode.Away,
    PRESET_PERMANENT_HOLD: eq3.Mode.Manual,
    PRESET_NO_HOLD: eq3.Mode.Auto,
    PRESET_OPEN: eq3.Mode.Open,
    PRESET_CLOSED: eq3.Mode.Closed,
}


DEVICE_SCHEMA = vol.Schema({vol.Required(CONF_MAC): cv.string})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_DEVICES): vol.Schema({cv.string: DEVICE_SCHEMA})}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the eQ-3 BLE thermostats."""
    devices = []

    for name, device_cfg in config[CONF_DEVICES].items():
        mac = device_cfg[CONF_MAC]
        devices.append(EQ3BTSmartThermostat(mac, name))

    add_entities(devices, True)


class EQ3BTSmartThermostat(ClimateEntity):
    """Representation of an eQ-3 Bluetooth Smart thermostat."""

    _attr_hvac_modes = list(HA_TO_EQ_HVAC)
    _attr_precision = PRECISION_HALVES
    _attr_preset_modes = list(HA_TO_EQ_PRESET)
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, mac: str, name: str) -> None:
        """Initialize the thermostat."""
        # We want to avoid name clash with this module.
        self._attr_name = name
        self._attr_unique_id = format_mac(mac)
        self._thermostat = eq3.Thermostat(mac)

    @property
    def available(self) -> bool:
        """Return if thermostat is available."""
        return self._thermostat.mode >= 0

    @property
    def current_temperature(self):
        """Can not report temperature, so return target_temperature."""
        return self.target_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._thermostat.target_temperature

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        self._thermostat.target_temperature = temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current operation mode."""
        if self._thermostat.mode < 0:
            return HVACMode.OFF
        return EQ_TO_HA_HVAC[self._thermostat.mode]

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set operation mode."""
        self._thermostat.mode = HA_TO_EQ_HVAC[hvac_mode]

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._thermostat.min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._thermostat.max_temp

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device specific state attributes."""
        return {
            ATTR_STATE_AWAY_END: self._thermostat.away_end,
            ATTR_STATE_LOCKED: self._thermostat.locked,
            ATTR_STATE_LOW_BAT: self._thermostat.low_battery,
            ATTR_STATE_VALVE: self._thermostat.valve_state,
            ATTR_STATE_WINDOW_OPEN: self._thermostat.window_open,
        }

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., home, away, temp.

        Requires ClimateEntityFeature.PRESET_MODE.
        """
        return EQ_TO_HA_PRESET.get(self._thermostat.mode)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_NONE:
            self.set_hvac_mode(HVACMode.HEAT)
        self._thermostat.mode = HA_TO_EQ_PRESET[preset_mode]

    def update(self) -> None:
        """Update the data from the thermostat."""

        try:
            self._thermostat.update()
        except eq3.BackendException as ex:
            _LOGGER.warning("Updating the state failed: %s", ex)
