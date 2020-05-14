"""Support for AVM Fritz!Box smarthome thermostate devices."""
import requests

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_COMFORT,
    PRESET_ECO,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_TEMPERATURE,
    CONF_DEVICES,
    PRECISION_HALVES,
    TEMP_CELSIUS,
)

from .const import (
    ATTR_STATE_BATTERY_LOW,
    ATTR_STATE_DEVICE_LOCKED,
    ATTR_STATE_HOLIDAY_MODE,
    ATTR_STATE_LOCKED,
    ATTR_STATE_SUMMER_MODE,
    ATTR_STATE_WINDOW_OPEN,
    CONF_CONNECTIONS,
    DOMAIN as FRITZBOX_DOMAIN,
    LOGGER,
)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

OPERATION_LIST = [HVAC_MODE_HEAT, HVAC_MODE_OFF]

MIN_TEMPERATURE = 8
MAX_TEMPERATURE = 28

PRESET_MANUAL = "manual"

# special temperatures for on/off in Fritz!Box API (modified by pyfritzhome)
ON_API_TEMPERATURE = 127.0
OFF_API_TEMPERATURE = 126.5
ON_REPORT_SET_TEMPERATURE = 30.0
OFF_REPORT_SET_TEMPERATURE = 0.0


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Fritzbox smarthome thermostat from config_entry."""
    entities = []
    devices = hass.data[FRITZBOX_DOMAIN][CONF_DEVICES]
    fritz = hass.data[FRITZBOX_DOMAIN][CONF_CONNECTIONS][config_entry.entry_id]

    for device in await hass.async_add_executor_job(fritz.get_devices):
        if device.has_thermostat and device.ain not in devices:
            entities.append(FritzboxThermostat(device, fritz))
            devices.add(device.ain)

    async_add_entities(entities)


class FritzboxThermostat(ClimateDevice):
    """The thermostat class for Fritzbox smarthome thermostates."""

    def __init__(self, device, fritz):
        """Initialize the thermostat."""
        self._device = device
        self._fritz = fritz
        self._current_temperature = self._device.actual_temperature
        self._target_temperature = self._device.target_temperature
        self._comfort_temperature = self._device.comfort_temperature
        self._eco_temperature = self._device.eco_temperature

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "name": self.name,
            "identifiers": {(FRITZBOX_DOMAIN, self._device.ain)},
            "manufacturer": self._device.manufacturer,
            "model": self._device.productname,
            "sw_version": self._device.fw_version,
        }

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return self._device.ain

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def available(self):
        """Return if thermostat is available."""
        return self._device.present

    @property
    def name(self):
        """Return the name of the device."""
        return self._device.name

    @property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def precision(self):
        """Return precision 0.5."""
        return PRECISION_HALVES

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._target_temperature == ON_API_TEMPERATURE:
            return ON_REPORT_SET_TEMPERATURE
        if self._target_temperature == OFF_API_TEMPERATURE:
            return OFF_REPORT_SET_TEMPERATURE
        return self._target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_HVAC_MODE in kwargs:
            hvac_mode = kwargs.get(ATTR_HVAC_MODE)
            self.set_hvac_mode(hvac_mode)
        elif ATTR_TEMPERATURE in kwargs:
            temperature = kwargs.get(ATTR_TEMPERATURE)
            self._device.set_target_temperature(temperature)

    @property
    def hvac_mode(self):
        """Return the current operation mode."""
        if (
            self._target_temperature == OFF_REPORT_SET_TEMPERATURE
            or self._target_temperature == OFF_API_TEMPERATURE
        ):
            return HVAC_MODE_OFF

        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return OPERATION_LIST

    def set_hvac_mode(self, hvac_mode):
        """Set new operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            self.set_temperature(temperature=OFF_REPORT_SET_TEMPERATURE)
        else:
            self.set_temperature(temperature=self._comfort_temperature)

    @property
    def preset_mode(self):
        """Return current preset mode."""
        if self._target_temperature == self._comfort_temperature:
            return PRESET_COMFORT
        if self._target_temperature == self._eco_temperature:
            return PRESET_ECO

    @property
    def preset_modes(self):
        """Return supported preset modes."""
        return [PRESET_ECO, PRESET_COMFORT]

    def set_preset_mode(self, preset_mode):
        """Set preset mode."""
        if preset_mode == PRESET_COMFORT:
            self.set_temperature(temperature=self._comfort_temperature)
        elif preset_mode == PRESET_ECO:
            self.set_temperature(temperature=self._eco_temperature)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return MIN_TEMPERATURE

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return MAX_TEMPERATURE

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        attrs = {
            ATTR_STATE_BATTERY_LOW: self._device.battery_low,
            ATTR_STATE_DEVICE_LOCKED: self._device.device_lock,
            ATTR_STATE_LOCKED: self._device.lock,
        }

        # the following attributes are available since fritzos 7
        if self._device.battery_level is not None:
            attrs[ATTR_BATTERY_LEVEL] = self._device.battery_level
        if self._device.holiday_active is not None:
            attrs[ATTR_STATE_HOLIDAY_MODE] = self._device.holiday_active
        if self._device.summer_active is not None:
            attrs[ATTR_STATE_SUMMER_MODE] = self._device.summer_active
        if ATTR_STATE_WINDOW_OPEN is not None:
            attrs[ATTR_STATE_WINDOW_OPEN] = self._device.window_open

        return attrs

    def update(self):
        """Update the data from the thermostat."""
        try:
            self._device.update()
            self._current_temperature = self._device.actual_temperature
            self._target_temperature = self._device.target_temperature
            self._comfort_temperature = self._device.comfort_temperature
            self._eco_temperature = self._device.eco_temperature
        except requests.exceptions.HTTPError as ex:
            LOGGER.warning("Fritzbox connection error: %s", ex)
            self._fritz.login()
