"""Entity bridging HA's Climate and the SDM API."""
import logging

from google_sdm.devices import SDMThermostat
from google_sdm.traits import (
    DeviceFanTrait,
    ThermostatEcoTrait,
    ThermostatModeTrait,
    ThermostatTemperatureSetpointTrait,
)

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    FAN_AUTO,
    FAN_ON,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_ECO,
    PRESET_NONE,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SDM_MODE_ECO = "MANUAL_ECO"
SDM_MODE_HEATCOOL = "HEATCOOL"
SDM_MODE_HEAT = "HEAT"
SDM_MODE_COOL = "COOL"
SDM_MODE_OFF = "OFF"

FAN_MODE_HASS_TO_SDM = {
    FAN_AUTO: DeviceFanTrait.TIMER_MODE_OFF,
    FAN_ON: DeviceFanTrait.TIMER_MODE_ON,
}

FAN_MODE_SDM_TO_HASS = {v: k for k, v in FAN_MODE_HASS_TO_SDM.items()}


MODE_HASS_TO_SDM = {
    HVAC_MODE_AUTO: SDM_MODE_HEATCOOL,
    HVAC_MODE_HEAT: SDM_MODE_HEAT,
    HVAC_MODE_COOL: SDM_MODE_COOL,
    HVAC_MODE_OFF: SDM_MODE_OFF,
}

MODE_SDM_TO_HASS = {v: k for k, v in MODE_HASS_TO_SDM.items()}

ACTION_SDM_TO_HASS = {
    "OFF": CURRENT_HVAC_IDLE,
    "HEATING": CURRENT_HVAC_HEAT,
    "COOLING": CURRENT_HVAC_COOL,
}

PRESET_MODES = [PRESET_NONE, PRESET_ECO]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the google_sdm climate device based on a config entry."""
    sdm_api = hass.data[DOMAIN][entry.entry_id]

    devices = None
    try:
        devices = await hass.async_add_job(sdm_api.populate_devices)
    except Exception as err:
        _LOGGER.exception(err)

    async_add_entities(devices, True)


class Climate(ClimateEntity):
    """Representation of HA device."""

    def __init__(self, sdm_device: SDMThermostat):
        """Initialize the thermostat."""
        self.device = sdm_device

        def update_listener(event):
            self.schedule_update_ha_state(True)

        self.device.register_event_listener(update_listener)
        self.device.register_update_listener(update_listener)
        self._fan_modes = [FAN_ON, FAN_AUTO]

        # Set the default supported features
        self._support_flags = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

        # Not all google_sdm devices support cooling and heating
        self._operation_list = [HVAC_MODE_OFF]

        if self.device.get_fan() and SDM_MODE_COOL in (
            self.device.get_thermostat_mode().available_modes
        ):
            self._operation_list.append(HVAC_MODE_AUTO)
            self._support_flags = self._support_flags | SUPPORT_TARGET_TEMPERATURE_RANGE

        # Add supported google_sdm thermostat features
        if SDM_MODE_HEAT in self.device.get_thermostat_mode().available_modes:
            self._operation_list.append(HVAC_MODE_HEAT)

        if SDM_MODE_COOL in self.device.get_thermostat_mode().available_modes:
            self._operation_list.append(HVAC_MODE_COOL)

        self._operation_list.append(HVAC_MODE_OFF)

        self._previous_hvac_mode = self.device.get_thermostat_mode().mode

        self._name = "Thermostat"
        if len(self.device.parentRelations) > 0:
            parent = self.device.parentRelations[0]
            if "displayName" in parent:
                self._name = parent["displayName"] + " Thermostat"

        # feature of device
        self._has_fan = self.device.get_fan() is not None
        if self._has_fan:
            self._support_flags = self._support_flags | SUPPORT_FAN_MODE

    @property
    def should_poll(self):
        """Do not need poll thanks using google_sdm streaming API."""
        return False

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self.device.name

    @property
    def device_info(self):
        """Return information about the device."""

        return {
            "identifiers": {(DOMAIN, self.device.name)},
            "name": self._name,
            "manufacturer": "Nest Labs",
            "model": "Thermostat",
        }

    @property
    def name(self):
        """Return the name of the google_sdm, if any."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.device.get_temperature().ambient_temperature_celsius

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        if self.device.get_thermostat_eco().mode == SDM_MODE_ECO:
            if self._previous_hvac_mode in MODE_SDM_TO_HASS:
                return MODE_SDM_TO_HASS[self._previous_hvac_mode]

            # previous_mode not supported so return the first compatible mode
            return self._operation_list[0]

        return MODE_SDM_TO_HASS[self.device.get_thermostat_mode().mode]

    @property
    def hvac_action(self):
        """Return the current hvac action."""
        return ACTION_SDM_TO_HASS[self.device.get_thermostat_hvac().status]

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        ts_mode = self.device.get_thermostat_mode().mode
        if (
            ts_mode != SDM_MODE_HEATCOOL
            and self.device.get_thermostat_eco().mode != SDM_MODE_ECO
        ):
            if ts_mode == SDM_MODE_COOL:
                return self.device.get_thermostat_temperature_setpoint().cool_celsius
            else:
                return self.device.get_thermostat_temperature_setpoint().heat_celsius
        return None

    @property
    def target_temperature_low(self):
        """Return the lower bound temperature we try to reach."""
        if self.device.get_thermostat_eco().mode == SDM_MODE_ECO:
            return self.device.get_thermostat_eco().heat_celsius
        if self.device.get_thermostat_mode().mode == SDM_MODE_HEATCOOL:
            return self.device.get_thermostat_temperature_setpoint().heat_celsius
        return None

    @property
    def target_temperature_high(self):
        """Return the upper bound temperature we try to reach."""
        if self.device.get_thermostat_eco().mode == SDM_MODE_ECO:
            return self.device.get_thermostat_eco().cool_celsius
        if self.device.get_thermostat_mode().mode == SDM_MODE_HEATCOOL:
            return self.device.get_thermostat_temperature_setpoint().cool_celsius
        return None

    def set_temperature(self, **kwargs):
        """Set new target temperature."""

        if self.preset_mode == PRESET_ECO:
            return

        temp = None
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if self.device.get_thermostat_mode().mode == SDM_MODE_HEATCOOL:
            if target_temp_low is not None and target_temp_high is not None:
                ThermostatTemperatureSetpointTrait.SetRange(
                    self.device,
                    cool_celsius=target_temp_high,
                    heat_celsius=target_temp_low,
                )
        else:
            temp = kwargs.get(ATTR_TEMPERATURE)
        try:
            if temp is not None:
                if self.device.get_thermostat_mode().mode == SDM_MODE_HEAT:
                    ThermostatTemperatureSetpointTrait.SetHeat(
                        self.device,
                        heat_celsius=temp,
                    )
                else:
                    ThermostatTemperatureSetpointTrait.SetCool(
                        self.device,
                        cool_celsius=temp,
                    )
        except Exception as api_error:
            _LOGGER.error("An error occurred while setting temperature: %s", api_error)
            # restore target temperature
            self.schedule_update_ha_state(True)

    def set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        ThermostatModeTrait.SetMode(self.device, mode=MODE_HASS_TO_SDM[hvac_mode])

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        hass_modes = []
        for mode in self.device.get_thermostat_mode().available_modes:
            hass_modes.append(MODE_SDM_TO_HASS[mode])
        return hass_modes

    @property
    def preset_mode(self):
        """Return current preset mode."""
        if self.device.get_thermostat_eco().mode == SDM_MODE_ECO:
            return PRESET_ECO

        return PRESET_NONE

    @property
    def preset_modes(self):
        """Return preset modes."""
        return PRESET_MODES

    def set_preset_mode(self, preset_mode):
        """Set preset mode."""
        need_eco = preset_mode in (PRESET_ECO)
        is_eco = self.device.get_thermostat_eco().mode == SDM_MODE_ECO

        if is_eco != need_eco:
            if need_eco:
                self._previous_hvac_mode = self.device.get_thermostat_mode().mode
                ThermostatEcoTrait.SetMode(
                    self.device, mode=ThermostatEcoTrait.ECO_MODE_ON
                )
            else:
                ThermostatEcoTrait.SetMode(
                    self.device, mode=ThermostatEcoTrait.ECO_MODE_OFF
                )
                ThermostatModeTrait.SetMode(self.device, mode=self._previous_hvac_mode)

    @property
    def fan_mode(self):
        """Return whether the fan is on."""
        if self._has_fan:
            # Return whether the fan is on
            return FAN_ON if self.device.get_fan().timer_mode == "ON" else FAN_AUTO
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
            DeviceFanTrait.SetTimer(
                self.device,
                timer_mode=FAN_MODE_HASS_TO_SDM[fan_mode],
                duration_seconds=15 * 60,
            )

    @property
    def min_temp(self):
        """Identify min_temp from docs."""
        return 10

    @property
    def max_temp(self) -> float:
        """Identify max_temp from docs."""
        return 32.22
