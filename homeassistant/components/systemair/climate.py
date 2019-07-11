"""Support for the SystemAIR HVAC."""
import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_FAN_MODE, ATTR_HVAC_MODE, ATTR_PRESET_MODE, FAN_HIGH, FAN_LOW,
    FAN_MEDIUM, FAN_OFF, HVAC_MODE_AUTO, HVAC_MODE_OFF, SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE, SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import ATTR_TEMPERATURE, CONF_NAME, TEMP_CELSIUS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    ATTR_CURRENT_HUMIDITY, ATTR_CURRENT_OPERATION, ATTR_TARGET_TEMPERATURE,
    PRESET_AUTO, PRESET_CROWDED, PRESET_FIREPLACE, PRESET_HOLIDAY, PRESET_IDLE,
    PRESET_MANUAL, PRESET_REFRESH, SIGNAL_SYSTEMAIR_UPDATE_DONE)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
})

_LOGGER = logging.getLogger(__name__)

HA_STATE_TO_SYSTEMAIR = {
    HVAC_MODE_AUTO: 'auto',
    HVAC_MODE_OFF: 'off',

}

SYSTEMAIR_TO_HA_STATE = {
    'auto': HVAC_MODE_AUTO,
    'off': HVAC_MODE_OFF,
}

HA_PRESET_TO_SYSTEMAIR = {
    PRESET_AUTO: 'auto',
    PRESET_MANUAL: 'manual',
    PRESET_CROWDED: 'crowded',
    PRESET_REFRESH: 'refresh',
    PRESET_FIREPLACE: 'fireplace',
    PRESET_HOLIDAY: 'holiday',
    PRESET_IDLE: 'idle'

}

FAN_MAXIMUM = 'maximum'

SYSTEMAIR_TO_HA_ATTR = {
    ATTR_TARGET_TEMPERATURE: ATTR_TEMPERATURE,
    ATTR_PRESET_MODE: ATTR_CURRENT_OPERATION
}

HA_SET_ATTR_TO_SYSTEMAIR = {}
HA_ATTR_TO_SYSTEMAIR = {}

PRESET_MODE = {}
FAN_MODE = {}

SYSTEMAIR_TRANSLATE_TO_HA = {
    ATTR_FAN_MODE: FAN_MODE,
    ATTR_PRESET_MODE: PRESET_MODE
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Systemair climate based on config_entry."""
    from systemair.savecair.const import (
        SENSOR_CURRENT_FAN_MODE,
        SENSOR_TARGET_TEMPERATURE,
        SENSOR_CURRENT_OPERATION,
        SENSOR_TEMPERATURE_EXTRACT,
        SENSOR_CUSTOM_OPERATION,
        SENSOR_CURRENT_HUMIDITY,
        SENSOR_MODE_CHANGE_REQUEST,
        SENSOR_CUSTOM_FAN_MODE
    )

    global HA_ATTR_TO_SYSTEMAIR
    HA_ATTR_TO_SYSTEMAIR = {
        ATTR_TARGET_TEMPERATURE: SENSOR_TARGET_TEMPERATURE,
        ATTR_FAN_MODE: SENSOR_CUSTOM_FAN_MODE,
        ATTR_PRESET_MODE: SENSOR_CURRENT_OPERATION,
        ATTR_TEMPERATURE: SENSOR_TEMPERATURE_EXTRACT,
        ATTR_HVAC_MODE: SENSOR_CUSTOM_OPERATION,
        ATTR_CURRENT_HUMIDITY: SENSOR_CURRENT_HUMIDITY,
    }

    global HA_SET_ATTR_TO_SYSTEMAIR
    HA_SET_ATTR_TO_SYSTEMAIR = {
        ATTR_TEMPERATURE: SENSOR_TARGET_TEMPERATURE,
        ATTR_PRESET_MODE: SENSOR_MODE_CHANGE_REQUEST,
        ATTR_FAN_MODE: SENSOR_CURRENT_FAN_MODE,
        ATTR_HVAC_MODE: SENSOR_CUSTOM_OPERATION
    }

    sab = hass.data[config["platform"]]
    async_add_entities([
        SystemAIRClimate(hass, sab)
    ])


class SystemAIRClimate(ClimateDevice):
    """Representation of a SystemAIR HVAC."""

    def __init__(self, hass, sab):
        """Initialize the climate device."""

        self._sab = sab
        self._list = {
            ATTR_HVAC_MODE: list(HA_STATE_TO_SYSTEMAIR),
            ATTR_FAN_MODE: [
                FAN_OFF,
                FAN_LOW,
                FAN_MEDIUM,
                FAN_HIGH,
                FAN_MAXIMUM
            ]
        }

        self._supported_features = SUPPORT_TARGET_TEMPERATURE
        self._supported_features |= SUPPORT_PRESET_MODE
        self._supported_features |= SUPPORT_FAN_MODE

        async def _handle_update(var):
            self.async_schedule_update_ha_state()

        # Register for dispatcher updates
        async_dispatcher_connect(
            hass, SIGNAL_SYSTEMAIR_UPDATE_DONE, _handle_update)

    def get(self, key):
        """Retrieve device settings from API library cache."""

        sa_key = HA_ATTR_TO_SYSTEMAIR.get(key)

        if sa_key not in self._sab.data:
            _LOGGER.warning("Missing attribute %s", sa_key)
            return None

        sa_value = self._sab.data[sa_key]

        return sa_value

    async def _set(self, settings):
        """Set device settings using API."""

        for ha_key in HA_SET_ATTR_TO_SYSTEMAIR:
            value = settings.get(ha_key)
            if value is None:
                continue

            sa_key = HA_SET_ATTR_TO_SYSTEMAIR.get(ha_key)

            await self._sab.set(sa_key, value)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._supported_features

    @property
    def name(self):
        """Return the name of the thermostat, if any."""
        return self._sab.name

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.get(ATTR_TEMPERATURE)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.get(ATTR_TARGET_TEMPERATURE)

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        await self._set(kwargs)

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self.get(ATTR_HVAC_MODE)

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return self._list.get(ATTR_HVAC_MODE)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode."""
        await self._set({ATTR_HVAC_MODE: hvac_mode})

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self.get(ATTR_FAN_MODE)

    async def async_set_fan_mode(self, fan_mode):
        """Set fan mode."""
        await self._set({ATTR_FAN_MODE: fan_mode})

    @property
    def fan_modes(self):
        """List of available fan modes."""
        return self._list.get(ATTR_FAN_MODE)

    @property
    def preset_mode(self):
        """Return the fan setting."""
        return self.get(ATTR_PRESET_MODE)

    async def async_set_preset_mode(self, preset_mode):
        """Set new target temperature."""
        await self._set({ATTR_PRESET_MODE: preset_mode})

    @property
    def preset_modes(self):
        """List of available swing modes."""
        return list(HA_PRESET_TO_SYSTEMAIR)

    async def async_update(self):
        """Retrieve latest state."""
        await self._sab.update()

    # @property
    # def device_info(self):
    #    """Return a device description for device registry."""
    #    return self._api.device_info
