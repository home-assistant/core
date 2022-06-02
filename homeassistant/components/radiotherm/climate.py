"""Support for Radio Thermostat wifi-enabled home thermostats."""
from __future__ import annotations

import logging

import radiotherm
from radiotherm.thermostat import CommonThermostat
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
from homeassistant.core import DOMAIN, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import CONF_HOLD_TEMP
from .data import RadioThermData, RadioThermUpdate

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

PRESET_MODE_TO_CODE = {"home": 0, "alternate": 1, "away": 2, "holiday": 3}

CODE_TO_PRESET_MODE = {0: "home", 1: "alternate", 2: "away", 3: "holiday"}

CODE_TO_HOLD_STATE = {0: False, 1: True}


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
    data: RadioThermData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [RadioThermostat(data.coordinator, data.tstat, data.name, data.hold_temp)]
    )


async def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Radio Thermostat."""
    hosts = []
    if CONF_HOST in config:
        hosts = config[CONF_HOST]
    else:
        hosts.append(
            await hass.async_add_executor_job(radiotherm.discover.discover_address)
        )

    if hosts is None:
        _LOGGER.error("No Radiotherm Thermostats detected")
        return

    hold_temp = config.get(CONF_HOLD_TEMP)
    for host in hosts:
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_HOST: host, CONF_HOLD_TEMP: hold_temp},
        )


class RadioThermostat(CoordinatorEntity, ClimateEntity):
    """Representation of a Radio Thermostat."""

    _attr_hvac_modes = OPERATION_LIST
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = TEMP_FAHRENHEIT
    _attr_precision = PRECISION_HALVES
    _attr_preset_modes = PRESET_MODES

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[RadioThermUpdate],
        device: CommonThermostat,
        name: str,
        hold_temp: int,
    ) -> None:
        """Initialize the thermostat."""
        super().__init__(coordinator)
        self.device = device
        self._target_temperature = None
        self._current_temperature = None
        self._current_humidity = None
        self._current_operation = HVACMode.OFF
        self._attr_name = name
        self._fstate: str | None = None
        self._tmode = None
        self._tstate: HVACAction | None = None
        self._hold_temp = hold_temp
        self._hold_set = False
        self._prev_temp = None
        self._program_mode: int | None = None
        self._is_away = False

        # Fan circulate mode is only supported by the CT80 models.
        self._is_model_ct80 = isinstance(self.device, radiotherm.thermostat.CT80)

    @property
    def data(self) -> RadioThermUpdate:
        """Returnt the last update."""
        return self.coordinator.data

    async def async_added_to_hass(self):
        """Register callbacks."""
        # Set the time on the device.  This shouldn't be in the
        # constructor because it's a network call.  We can't put it in
        # update() because calling it will clear any temporary mode or
        # temperature in the thermostat.  So add it as a future job
        # for the event loop to run.
        self.hass.async_add_job(self.set_time)

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        return {ATTR_FAN_ACTION: self._fstate}

    @property
    def fan_modes(self):
        """List of available fan modes."""
        if self._is_model_ct80:
            return CT80_FAN_OPERATION_LIST
        return CT30_FAN_OPERATION_LIST

    def set_fan_mode(self, fan_mode):
        """Turn fan on/off."""
        if (code := FAN_MODE_TO_CODE.get(fan_mode)) is not None:
            self.device.fmode = code

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported."""
        if self.hvac_mode == HVACMode.OFF:
            return None
        return self._tstate

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        if self._program_mode == 0:
            return PRESET_HOME
        if self._program_mode == 1:
            return PRESET_ALTERNATE
        if self._program_mode == 2:
            return PRESET_AWAY
        if self._program_mode == 3:
            return PRESET_HOLIDAY

    def _handle_coordinator_update(self) -> None:
        """Update and validate the data from the thermostat."""
        # Radio thermostats are very slow, and sometimes don't respond
        # very quickly.  So we need to keep the number of calls to them
        # to a bare minimum or we'll hit the Home Assistant 10 sec warning.  We
        # have to make one call to /tstat to get temps but we'll try and
        # keep the other calls to a minimum.  Even with this, these
        # thermostats tend to time out sometimes when they're actively
        # heating or cooling.
        data = self.data.tstat
        if self._is_model_ct80:
            self._attr_current_humidity = self.data.humidity
            self._program_mode = data["program_mode"]
            self._attr_preset_mode = CODE_TO_PRESET_MODE[data["program_mode"]]

        # Map thermostat values into various STATE_ flags.
        self._current_temperature = data["temp"]
        self._attr_fan_mode = CODE_TO_FAN_MODE[data["fmode"]]
        self._fstate = CODE_TO_FAN_STATE[data["fstate"]]
        self._attr_hvac_mode = CODE_TO_TEMP_MODE[data["tmode"]]
        self._tstate = CODE_TO_TEMP_STATE[data["tstate"]]
        self._hold_set = CODE_TO_HOLD_STATE[data["hold"]]

        if self.hvac_mode == HVACMode.COOL:
            self._target_temperature = data["t_cool"]
        elif self.hvac_mode == HVACMode.HEAT:
            self._target_temperature = data["t_heat"]
        elif self.hvac_mode == HVACMode.AUTO:
            # This doesn't really work - tstate is only set if the HVAC is
            # active. If it's idle, we don't know what to do with the target
            # temperature.
            if self._tstate == HVACAction.COOLING:
                self._target_temperature = data["t_cool"]
            elif self._tstate == HVACAction.HEATING:
                self._target_temperature = data["t_heat"]
        return super()._handle_coordinator_update()

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        temperature = round_temp(temperature)

        if self._current_operation == HVACMode.COOL:
            self.device.t_cool = temperature
        elif self._current_operation == HVACMode.HEAT:
            self.device.t_heat = temperature
        elif self._current_operation == HVACMode.AUTO:
            if self._tstate == HVACAction.COOLING:
                self.device.t_cool = temperature
            elif self._tstate == HVACAction.HEATING:
                self.device.t_heat = temperature

        # Only change the hold if requested or if hold mode was turned
        # on and we haven't set it yet.
        if kwargs.get("hold_changed", False) or not self._hold_set:
            if self._hold_temp:
                self.device.hold = 1
                self._hold_set = True
            else:
                self.device.hold = 0

    def set_time(self):
        """Set device time."""
        # Calling this clears any local temperature override and
        # reverts to the scheduled temperature.
        now = dt_util.now()
        self.device.time = {
            "day": now.weekday(),
            "hour": now.hour,
            "minute": now.minute,
        }

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set operation mode (auto, cool, heat, off)."""
        if hvac_mode in (HVACMode.OFF, HVACMode.AUTO):
            self.device.tmode = TEMP_MODE_TO_CODE[hvac_mode]

        # Setting t_cool or t_heat automatically changes tmode.
        elif hvac_mode == HVACMode.COOL:
            self.device.t_cool = self._target_temperature
        elif hvac_mode == HVACMode.HEAT:
            self.device.t_heat = self._target_temperature

    def set_preset_mode(self, preset_mode):
        """Set Preset mode (Home, Alternate, Away, Holiday)."""
        if preset_mode in PRESET_MODES:
            self.device.program_mode = PRESET_MODE_TO_CODE[preset_mode]
        else:
            _LOGGER.error(
                "Preset_mode %s not in PRESET_MODES",
                preset_mode,
            )
