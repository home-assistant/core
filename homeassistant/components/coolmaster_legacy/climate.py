"""coolmaster_legacy platform to control of CoolMaster Climate Devices."""

import logging

from pycoolmaster import CoolMaster

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

from .const import AVAILABLE_MODES, DOMAIN, CONF_SERIAL_PORT, CONF_BAUDRATE

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE

CM_TO_HA_STATE = {
    "heat": HVAC_MODE_HEAT,
    "cool": HVAC_MODE_COOL,
    "auto": HVAC_MODE_HEAT_COOL,
    "dry": HVAC_MODE_DRY,
    "fan": HVAC_MODE_FAN_ONLY,
}

HA_STATE_TO_CM = {value: key for key, value in CM_TO_HA_STATE.items()}

FAN_MODES = ["low", "med", "high", "auto", "top"]
SWING_MODES = ["auto", "horizontal", "30", "45", "60", "vertical"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the CoolMaster climate platform."""
    port = config_entry.data[CONF_SERIAL_PORT]
    baud = config_entry.data[CONF_BAUDRATE]
    cool = CoolMaster(port, baud)
    devices = await hass.async_add_executor_job(cool.devices)

    all_devices = [CoolmasterClimate(device) for device in devices]

    async_add_devices(all_devices, True)


class CoolmasterClimate(ClimateDevice):
    """Representation of a coolmaster_legacy climate device."""

    def __init__(self, device):
        """Initialize the climate device."""
        self._device = device
        self._uid = device.uid
        self._hvac_modes = AVAILABLE_MODES
        self._hvac_mode = None
        self._target_temperature = None
        self._current_temperature = None
        self._current_fan_mode = None
        self._current_operation = None
        self._swing = None
        self._on = None
        self._unit = None
        _LOGGER.debug("Initialized device %s", device.uid)

    def update(self):
        """Pull state from CoolMaster."""
        status = self._device.status
        self._target_temperature = status["thermostat"]
        self._current_temperature = status["temperature"]
        self._current_fan_mode = status["fan_speed"]
        self._on = status["is_on"]

        device_mode = status["mode"]
        if self._on:
            self._hvac_mode = CM_TO_HA_STATE[device_mode]
        else:
            self._hvac_mode = HVAC_MODE_OFF

        if status["unit"] == "celsius":
            self._unit = TEMP_CELSIUS
        else:
            self._unit = TEMP_FAHRENHEIT

        self._swing = status["swing"]

    @property
    def device_info(self):
        """Return device info for this device."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "CoolAutomation",
            "model": "CoolMaster",
        }

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._uid

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the climate device."""
        return self.unique_id

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we are trying to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return hvac target hvac state."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return self._hvac_modes

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return FAN_MODES

    @property
    def swing_modes(self):
        """Return the list of available swing modes."""
        return SWING_MODES

    @property
    def precision(self):
        """Return the temperature precision."""
        return PRECISION_WHOLE

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            _LOGGER.debug("Setting temp of %s to %s", self.unique_id, str(temp))
            self._device.set_thermostat(str(temp))

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        _LOGGER.debug("Setting fan mode of %s to %s", self.unique_id, fan_mode)
        self._device.set_fan_speed(fan_mode)

    def set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        _LOGGER.debug("Setting swing mode of %s to %s", self.unique_id, swing_mode)
        self._device.set_swing(swing_mode)

    def set_hvac_mode(self, hvac_mode):
        """Set new operation mode."""
        _LOGGER.debug("Setting operation mode of %s to %s", self.unique_id, hvac_mode)

        if hvac_mode == HVAC_MODE_OFF:
            self.turn_off()
        else:
            self._device.set_mode(HA_STATE_TO_CM[hvac_mode])
            self.turn_on()

    def turn_on(self):
        """Turn on."""
        _LOGGER.debug("Turning %s on", self.unique_id)
        self._device.turn_on()

    def turn_off(self):
        """Turn off."""
        _LOGGER.debug("Turning %s off", self.unique_id)
        self._device.turn_off()
