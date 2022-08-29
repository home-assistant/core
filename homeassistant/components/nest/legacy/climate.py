"""Legacy Works with Nest climate implementation."""
# mypy: ignore-errors

import logging

from nest.nest import APIError
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_ON,
    PRESET_AWAY,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_SCAN_INTERVAL,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

from .const import DATA_NEST, DOMAIN, SIGNAL_NEST_UPDATE

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=1))}
)

NEST_MODE_HEAT_COOL = "heat-cool"
NEST_MODE_ECO = "eco"
NEST_MODE_HEAT = "heat"
NEST_MODE_COOL = "cool"
NEST_MODE_OFF = "off"

MODE_HASS_TO_NEST = {
    HVACMode.AUTO: NEST_MODE_HEAT_COOL,
    HVACMode.HEAT: NEST_MODE_HEAT,
    HVACMode.COOL: NEST_MODE_COOL,
    HVACMode.OFF: NEST_MODE_OFF,
}

MODE_NEST_TO_HASS = {v: k for k, v in MODE_HASS_TO_NEST.items()}

ACTION_NEST_TO_HASS = {
    "off": HVACAction.IDLE,
    "heating": HVACAction.HEATING,
    "cooling": HVACAction.COOLING,
}

PRESET_AWAY_AND_ECO = "Away and Eco"

PRESET_MODES = [PRESET_NONE, PRESET_AWAY, PRESET_ECO, PRESET_AWAY_AND_ECO]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Nest thermostat.

    No longer in use.
    """


async def async_setup_legacy_entry(hass, entry, async_add_entities) -> None:
    """Set up the Nest climate device based on a config entry."""
    temp_unit = hass.config.units.temperature_unit

    thermostats = await hass.async_add_executor_job(hass.data[DATA_NEST].thermostats)

    all_devices = [
        NestThermostat(structure, device, temp_unit)
        for structure, device in thermostats
    ]

    async_add_entities(all_devices, True)


class NestThermostat(ClimateEntity):
    """Representation of a Nest thermostat."""

    _attr_should_poll = False

    def __init__(self, structure, device, temp_unit):
        """Initialize the thermostat."""
        self._unit = temp_unit
        self.structure = structure
        self.device = device
        self._fan_modes = [FAN_ON, FAN_AUTO]

        # Set the default supported features
        self._support_flags = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        )

        # Not all nest devices support cooling and heating remove unused
        self._operation_list = []

        if self.device.can_heat and self.device.can_cool:
            self._operation_list.append(HVACMode.AUTO)
            self._support_flags |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE

        # Add supported nest thermostat features
        if self.device.can_heat:
            self._operation_list.append(HVACMode.HEAT)

        if self.device.can_cool:
            self._operation_list.append(HVACMode.COOL)

        self._operation_list.append(HVACMode.OFF)

        # feature of device
        self._has_fan = self.device.has_fan
        if self._has_fan:
            self._support_flags |= ClimateEntityFeature.FAN_MODE

        # data attributes
        self._away = None
        self._location = None
        self._name = None
        self._humidity = None
        self._target_temperature = None
        self._temperature = None
        self._temperature_scale = None
        self._mode = None
        self._action = None
        self._fan = None
        self._eco_temperature = None
        self._is_locked = None
        self._locked_temperature = None
        self._min_temperature = None
        self._max_temperature = None

    async def async_added_to_hass(self):
        """Register update signal handler."""

        async def async_update_state():
            """Update device state."""
            await self.async_update_ha_state(True)

        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_NEST_UPDATE, async_update_state)
        )

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self.device.serial

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id)},
            manufacturer="Nest Labs",
            model="Thermostat",
            name=self.device.name_long,
            sw_version=self.device.software_version,
        )

    @property
    def name(self):
        """Return the name of the nest, if any."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._temperature_scale

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation ie. heat, cool, idle."""
        if self._mode == NEST_MODE_ECO:
            if self.device.previous_mode in MODE_NEST_TO_HASS:
                return MODE_NEST_TO_HASS[self.device.previous_mode]

            # previous_mode not supported so return the first compatible mode
            return self._operation_list[0]

        return MODE_NEST_TO_HASS[self._mode]

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current hvac action."""
        return ACTION_NEST_TO_HASS[self._action]

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._mode not in (NEST_MODE_HEAT_COOL, NEST_MODE_ECO):
            return self._target_temperature
        return None

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        if self._mode == NEST_MODE_ECO:
            return self._eco_temperature[0]
        if self._mode == NEST_MODE_HEAT_COOL:
            return self._target_temperature[0]
        return None

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        if self._mode == NEST_MODE_ECO:
            return self._eco_temperature[1]
        if self._mode == NEST_MODE_HEAT_COOL:
            return self._target_temperature[1]
        return None

    def set_temperature(self, **kwargs):
        """Set new target temperature."""

        temp = None
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if self._mode == NEST_MODE_HEAT_COOL:
            if target_temp_low is not None and target_temp_high is not None:
                temp = (target_temp_low, target_temp_high)
                _LOGGER.debug("Nest set_temperature-output-value=%s", temp)
        else:
            temp = kwargs.get(ATTR_TEMPERATURE)
            _LOGGER.debug("Nest set_temperature-output-value=%s", temp)
        try:
            if temp is not None:
                self.device.target = temp
        except APIError as api_error:
            _LOGGER.error("An error occurred while setting temperature: %s", api_error)
            # restore target temperature
            self.schedule_update_ha_state(True)

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set operation mode."""
        self.device.mode = MODE_HASS_TO_NEST[hvac_mode]

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """List of available operation modes."""
        return self._operation_list

    @property
    def preset_mode(self):
        """Return current preset mode."""
        if self._away and self._mode == NEST_MODE_ECO:
            return PRESET_AWAY_AND_ECO

        if self._away:
            return PRESET_AWAY

        if self._mode == NEST_MODE_ECO:
            return PRESET_ECO

        return PRESET_NONE

    @property
    def preset_modes(self):
        """Return preset modes."""
        return PRESET_MODES

    def set_preset_mode(self, preset_mode):
        """Set preset mode."""
        if preset_mode == self.preset_mode:
            return

        need_away = preset_mode in (PRESET_AWAY, PRESET_AWAY_AND_ECO)
        need_eco = preset_mode in (PRESET_ECO, PRESET_AWAY_AND_ECO)
        is_away = self._away
        is_eco = self._mode == NEST_MODE_ECO

        if is_away != need_away:
            self.structure.away = need_away

        if is_eco != need_eco:
            if need_eco:
                self.device.mode = NEST_MODE_ECO
            else:
                self.device.mode = self.device.previous_mode

    @property
    def fan_mode(self):
        """Return whether the fan is on."""
        if self._has_fan:
            # Return whether the fan is on
            return FAN_ON if self._fan else FAN_AUTO
        # No Fan available so disable slider
        return None

    @property
    def fan_modes(self):
        """List of available fan modes."""
        if self._has_fan:
            return self._fan_modes
        return None

    def set_fan_mode(self, fan_mode):
        """Turn fan on/off."""
        if self._has_fan:
            self.device.fan = fan_mode.lower()

    @property
    def min_temp(self):
        """Identify min_temp in Nest API or defaults if not available."""
        return self._min_temperature

    @property
    def max_temp(self):
        """Identify max_temp in Nest API or defaults if not available."""
        return self._max_temperature

    def update(self):
        """Cache value from Python-nest."""
        self._location = self.device.where
        self._name = self.device.name
        self._humidity = self.device.humidity
        self._temperature = self.device.temperature
        self._mode = self.device.mode
        self._action = self.device.hvac_state
        self._target_temperature = self.device.target
        self._fan = self.device.fan
        self._away = self.structure.away == "away"
        self._eco_temperature = self.device.eco_temperature
        self._locked_temperature = self.device.locked_temperature
        self._min_temperature = self.device.min_temperature
        self._max_temperature = self.device.max_temperature
        self._is_locked = self.device.is_locked
        if self.device.temperature_scale == "C":
            self._temperature_scale = TEMP_CELSIUS
        else:
            self._temperature_scale = TEMP_FAHRENHEIT
