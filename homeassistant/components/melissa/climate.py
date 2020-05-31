"""Support for Melissa Climate A/C."""
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, TEMP_CELSIUS

from . import DATA_MELISSA

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_FAN_MODE | SUPPORT_TARGET_TEMPERATURE

OP_MODES = [
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_OFF,
]

FAN_MODES = [FAN_AUTO, FAN_HIGH, FAN_MEDIUM, FAN_LOW]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Iterate through and add all Melissa devices."""
    api = hass.data[DATA_MELISSA]
    devices = (await api.async_fetch_devices()).values()

    all_devices = []

    for device in devices:
        if device["type"] == "melissa":
            all_devices.append(MelissaClimate(api, device["serial_number"], device))

    async_add_entities(all_devices)


class MelissaClimate(ClimateEntity):
    """Representation of a Melissa Climate device."""

    def __init__(self, api, serial_number, init_data):
        """Initialize the climate device."""
        self._name = init_data["name"]
        self._api = api
        self._serial_number = serial_number
        self._data = init_data["controller_log"]
        self._state = None
        self._cur_settings = None

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def fan_mode(self):
        """Return the current fan mode."""
        if self._cur_settings is not None:
            return self.melissa_fan_to_hass(self._cur_settings[self._api.FAN])

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._data:
            return self._data[self._api.TEMP]

    @property
    def current_humidity(self):
        """Return the current humidity value."""
        if self._data:
            return self._data[self._api.HUMIDITY]

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return PRECISION_WHOLE

    @property
    def hvac_mode(self):
        """Return the current operation mode."""
        if self._cur_settings is None:
            return None

        is_on = self._cur_settings[self._api.STATE] in (
            self._api.STATE_ON,
            self._api.STATE_IDLE,
        )

        if not is_on:
            return HVAC_MODE_OFF

        return self.melissa_op_to_hass(self._cur_settings[self._api.MODE])

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return OP_MODES

    @property
    def fan_modes(self):
        """List of available fan modes."""
        return FAN_MODES

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._cur_settings is None:
            return None
        return self._cur_settings[self._api.TEMP]

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def min_temp(self):
        """Return the minimum supported temperature for the thermostat."""
        return 16

    @property
    def max_temp(self):
        """Return the maximum supported temperature for the thermostat."""
        return 30

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        await self.async_send({self._api.TEMP: temp})

    async def async_set_fan_mode(self, fan_mode):
        """Set fan mode."""
        melissa_fan_mode = self.hass_fan_to_melissa(fan_mode)
        await self.async_send({self._api.FAN: melissa_fan_mode})

    async def async_set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self.async_send({self._api.STATE: self._api.STATE_OFF})
            return

        mode = self.hass_mode_to_melissa(hvac_mode)
        await self.async_send(
            {self._api.MODE: mode, self._api.STATE: self._api.STATE_ON}
        )

    async def async_send(self, value):
        """Send action to service."""
        try:
            old_value = self._cur_settings.copy()
            self._cur_settings.update(value)
        except AttributeError:
            old_value = None
        if not await self._api.async_send(self._serial_number, self._cur_settings):
            self._cur_settings = old_value

    async def async_update(self):
        """Get latest data from Melissa."""
        try:
            self._data = (await self._api.async_status(cached=True))[
                self._serial_number
            ]
            self._cur_settings = (
                await self._api.async_cur_settings(self._serial_number)
            )["controller"]["_relation"]["command_log"]
        except KeyError:
            _LOGGER.warning("Unable to update entity %s", self.entity_id)

    def melissa_op_to_hass(self, mode):
        """Translate Melissa modes to hass states."""
        if mode == self._api.MODE_HEAT:
            return HVAC_MODE_HEAT
        if mode == self._api.MODE_COOL:
            return HVAC_MODE_COOL
        if mode == self._api.MODE_DRY:
            return HVAC_MODE_DRY
        if mode == self._api.MODE_FAN:
            return HVAC_MODE_FAN_ONLY
        _LOGGER.warning("Operation mode %s could not be mapped to hass", mode)
        return None

    def melissa_fan_to_hass(self, fan):
        """Translate Melissa fan modes to hass modes."""
        if fan == self._api.FAN_AUTO:
            return HVAC_MODE_AUTO
        if fan == self._api.FAN_LOW:
            return FAN_LOW
        if fan == self._api.FAN_MEDIUM:
            return FAN_MEDIUM
        if fan == self._api.FAN_HIGH:
            return FAN_HIGH
        _LOGGER.warning("Fan mode %s could not be mapped to hass", fan)
        return None

    def hass_mode_to_melissa(self, mode):
        """Translate hass states to melissa modes."""
        if mode == HVAC_MODE_HEAT:
            return self._api.MODE_HEAT
        if mode == HVAC_MODE_COOL:
            return self._api.MODE_COOL
        if mode == HVAC_MODE_DRY:
            return self._api.MODE_DRY
        if mode == HVAC_MODE_FAN_ONLY:
            return self._api.MODE_FAN
        _LOGGER.warning("Melissa have no setting for %s mode", mode)

    def hass_fan_to_melissa(self, fan):
        """Translate hass fan modes to melissa modes."""
        if fan == HVAC_MODE_AUTO:
            return self._api.FAN_AUTO
        if fan == FAN_LOW:
            return self._api.FAN_LOW
        if fan == FAN_MEDIUM:
            return self._api.FAN_MEDIUM
        if fan == FAN_HIGH:
            return self._api.FAN_HIGH
        _LOGGER.warning("Melissa have no setting for %s fan mode", fan)
