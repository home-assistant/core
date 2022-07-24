"""Support for Radio Thermostat wifi-enabled home thermostats."""
from __future__ import annotations

import logging
from typing import Any

import radiotherm
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_OFF,
    FAN_ON,
    PRESET_AWAY,
    PRESET_HOME,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    PRECISION_HALVES,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN
from .coordinator import RadioThermUpdateCoordinator
from .entity import RadioThermostatEntity

_LOGGER = logging.getLogger(__name__)

ATTR_FAN_ACTION = "fan_action"

PRESET_HOLIDAY = "holiday"

PRESET_ALTERNATE = "alternate"

STATE_CIRCULATE = "circulate"

PRESET_MODES = [PRESET_HOME, PRESET_ALTERNATE, PRESET_AWAY, PRESET_HOLIDAY]

OPERATION_LIST = [HVACMode.AUTO, HVACMode.COOL, HVACMode.HEAT, HVACMode.OFF]
CT30_FAN_OPERATION_LIST = [FAN_ON, FAN_AUTO]
CT80_FAN_OPERATION_LIST = [FAN_ON, STATE_CIRCULATE, FAN_AUTO]

# Mappings from radiotherm json data codes to and from Home Assistant state
# flags.  CODE is the thermostat integer code and these map to and
# from Home Assistant state flags.

# Programmed temperature mode of the thermostat.
CODE_TO_TEMP_MODE = {
    0: HVACMode.OFF,
    1: HVACMode.HEAT,
    2: HVACMode.COOL,
    3: HVACMode.AUTO,
}
TEMP_MODE_TO_CODE = {v: k for k, v in CODE_TO_TEMP_MODE.items()}

# Programmed fan mode (circulate is supported by CT80 models)
CODE_TO_FAN_MODE = {0: FAN_AUTO, 1: STATE_CIRCULATE, 2: FAN_ON}

FAN_MODE_TO_CODE = {v: k for k, v in CODE_TO_FAN_MODE.items()}

# Active thermostat state (is it heating or cooling?).  In the future
# this should probably made into heat and cool binary sensors.
CODE_TO_TEMP_STATE = {0: HVACAction.IDLE, 1: HVACAction.HEATING, 2: HVACAction.COOLING}

# Active fan state.  This is if the fan is actually on or not.  In the
# future this should probably made into a binary sensor for the fan.
CODE_TO_FAN_STATE = {0: FAN_OFF, 1: FAN_ON}

PRESET_MODE_TO_CODE = {
    PRESET_HOME: 0,
    PRESET_ALTERNATE: 1,
    PRESET_AWAY: 2,
    PRESET_HOLIDAY: 3,
}

CODE_TO_PRESET_MODE = {v: k for k, v in PRESET_MODE_TO_CODE.items()}


PARALLEL_UPDATES = 1

CONF_HOLD_TEMP = "hold_temp"


def round_temp(temperature):
    """Round a temperature to the resolution of the thermostat.

    RadioThermostats can handle 0.5 degree temps so the input
    temperature is rounded to that value and returned.
    """
    return round(temperature * 2.0) / 2.0


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_HOLD_TEMP, default=False): cv.boolean,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate for a radiotherm device."""
    coordinator: RadioThermUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RadioThermostat(coordinator)])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Radio Thermostat."""
    _LOGGER.warning(
        # config flow added in 2022.7 and should be removed in 2022.9
        "Configuration of the Radio Thermostat climate platform in YAML is deprecated and "
        "will be removed in Home Assistant 2022.9; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )
    hosts: list[str] = []
    if CONF_HOST in config:
        hosts = config[CONF_HOST]
    else:
        hosts.append(
            await hass.async_add_executor_job(radiotherm.discover.discover_address)
        )

    if not hosts:
        _LOGGER.error("No Radiotherm Thermostats detected")
        return

    for host in hosts:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={CONF_HOST: host},
            )
        )


class RadioThermostat(RadioThermostatEntity, ClimateEntity):
    """Representation of a Radio Thermostat."""

    _attr_hvac_modes = OPERATION_LIST
    _attr_temperature_unit = TEMP_FAHRENHEIT
    _attr_precision = PRECISION_HALVES

    def __init__(self, coordinator: RadioThermUpdateCoordinator) -> None:
        """Initialize the thermostat."""
        super().__init__(coordinator)
        self._attr_name = self.init_data.name
        self._attr_unique_id = self.init_data.mac
        self._attr_fan_modes = CT30_FAN_OPERATION_LIST
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        )
        if not isinstance(self.device, radiotherm.thermostat.CT80):
            return
        self._attr_fan_modes = CT80_FAN_OPERATION_LIST
        self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
        self._attr_preset_modes = PRESET_MODES

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Turn fan on/off."""
        if (code := FAN_MODE_TO_CODE.get(fan_mode)) is None:
            raise ValueError(f"{fan_mode} is not a valid fan mode")
        await self.hass.async_add_executor_job(self._set_fan_mode, code)
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _set_fan_mode(self, code: int) -> None:
        """Turn fan on/off."""
        self.device.fmode = code

    @callback
    def _process_data(self) -> None:
        """Update and validate the data from the thermostat."""
        data = self.data.tstat
        if isinstance(self.device, radiotherm.thermostat.CT80):
            self._attr_current_humidity = self.data.humidity
            self._attr_preset_mode = CODE_TO_PRESET_MODE[data["program_mode"]]
        # Map thermostat values into various STATE_ flags.
        self._attr_current_temperature = data["temp"]
        self._attr_fan_mode = CODE_TO_FAN_MODE[data["fmode"]]
        self._attr_extra_state_attributes = {
            ATTR_FAN_ACTION: CODE_TO_FAN_STATE[data["fstate"]]
        }
        self._attr_hvac_mode = CODE_TO_TEMP_MODE[data["tmode"]]
        if self.hvac_mode == HVACMode.OFF:
            self._attr_hvac_action = None
        else:
            self._attr_hvac_action = CODE_TO_TEMP_STATE[data["tstate"]]
        if self.hvac_mode == HVACMode.COOL:
            self._attr_target_temperature = data["t_cool"]
        elif self.hvac_mode == HVACMode.HEAT:
            self._attr_target_temperature = data["t_heat"]
        elif self.hvac_mode == HVACMode.AUTO:
            # This doesn't really work - tstate is only set if the HVAC is
            # active. If it's idle, we don't know what to do with the target
            # temperature.
            if self.hvac_action == HVACAction.COOLING:
                self._attr_target_temperature = data["t_cool"]
            elif self.hvac_action == HVACAction.HEATING:
                self._attr_target_temperature = data["t_heat"]

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self.hass.async_add_executor_job(self._set_temperature, temperature)
        self._attr_target_temperature = temperature
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _set_temperature(self, temperature: int) -> None:
        """Set new target temperature."""
        temperature = round_temp(temperature)
        if self.hvac_mode == HVACMode.COOL:
            self.device.t_cool = temperature
        elif self.hvac_mode == HVACMode.HEAT:
            self.device.t_heat = temperature
        elif self.hvac_mode == HVACMode.AUTO:
            if self.hvac_action == HVACAction.COOLING:
                self.device.t_cool = temperature
            elif self.hvac_action == HVACAction.HEATING:
                self.device.t_heat = temperature

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set operation mode (auto, cool, heat, off)."""
        await self.hass.async_add_executor_job(self._set_hvac_mode, hvac_mode)
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set operation mode (auto, cool, heat, off)."""
        if hvac_mode in (HVACMode.OFF, HVACMode.AUTO):
            self.device.tmode = TEMP_MODE_TO_CODE[hvac_mode]
        # Setting t_cool or t_heat automatically changes tmode.
        elif hvac_mode == HVACMode.COOL:
            self.device.t_cool = self.target_temperature
        elif hvac_mode == HVACMode.HEAT:
            self.device.t_heat = self.target_temperature

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set Preset mode (Home, Alternate, Away, Holiday)."""
        if preset_mode not in PRESET_MODES:
            raise ValueError(f"{preset_mode} is not a valid preset_mode")
        await self.hass.async_add_executor_job(self._set_preset_mode, preset_mode)
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _set_preset_mode(self, preset_mode: str) -> None:
        """Set Preset mode (Home, Alternate, Away, Holiday)."""
        assert isinstance(self.device, radiotherm.thermostat.CT80)
        self.device.program_mode = PRESET_MODE_TO_CODE[preset_mode]
