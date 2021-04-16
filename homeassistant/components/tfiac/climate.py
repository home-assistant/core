"""Climate platform that offers a climate device for the TFIAC protocol."""
from concurrent import futures
from datetime import timedelta
import logging

from pytfiac import Tfiac
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
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
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
)
from homeassistant.const import ATTR_TEMPERATURE, CONF_HOST, TEMP_FAHRENHEIT
import homeassistant.helpers.config_validation as cv

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_HOST): cv.string})

_LOGGER = logging.getLogger(__name__)

MIN_TEMP = 61
MAX_TEMP = 88

HVAC_MAP = {
    HVAC_MODE_HEAT: "heat",
    HVAC_MODE_AUTO: "selfFeel",
    HVAC_MODE_DRY: "dehumi",
    HVAC_MODE_FAN_ONLY: "fan",
    HVAC_MODE_COOL: "cool",
    HVAC_MODE_OFF: "off",
}

HVAC_MAP_REV = {v: k for k, v in HVAC_MAP.items()}

SUPPORT_FAN = [FAN_AUTO, FAN_HIGH, FAN_MEDIUM, FAN_LOW]
SUPPORT_SWING = [SWING_OFF, SWING_HORIZONTAL, SWING_VERTICAL, SWING_BOTH]

SUPPORT_FLAGS = SUPPORT_FAN_MODE | SUPPORT_SWING_MODE | SUPPORT_TARGET_TEMPERATURE

CURR_TEMP = "current_temp"
TARGET_TEMP = "target_temp"
OPERATION_MODE = "operation"
FAN_MODE = "fan_mode"
SWING_MODE = "swing_mode"
ON_MODE = "is_on"


async def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the TFIAC climate device."""
    tfiac_client = Tfiac(config[CONF_HOST])
    try:
        await tfiac_client.update()
    except futures.TimeoutError:
        _LOGGER.error("Unable to connect to %s", config[CONF_HOST])
        return
    async_add_devices([TfiacClimate(hass, tfiac_client)])


class TfiacClimate(ClimateEntity):
    """TFIAC class."""

    def __init__(self, hass, client):
        """Init class."""
        self._client = client
        self._available = True

    @property
    def available(self):
        """Return if the device is available."""
        return self._available

    async def async_update(self):
        """Update status via socket polling."""
        try:
            await self._client.update()
            self._available = True
        except futures.TimeoutError:
            self._available = False

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return MIN_TEMP

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return MAX_TEMP

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._client.name

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._client.status["target_temp"]

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._client.status["current_temp"]

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if self._client.status[ON_MODE] != "on":
            return HVAC_MODE_OFF

        state = self._client.status["operation"]
        return HVAC_MAP_REV.get(state)

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return list(HVAC_MAP)

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._client.status["fan_mode"].lower()

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return SUPPORT_FAN

    @property
    def swing_mode(self):
        """Return the swing setting."""
        return self._client.status["swing_mode"].lower()

    @property
    def swing_modes(self):
        """List of available swing modes."""
        return SUPPORT_SWING

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self._client.set_state(TARGET_TEMP, temp)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self._client.set_state(ON_MODE, "off")
        else:
            await self._client.set_state(OPERATION_MODE, HVAC_MAP[hvac_mode])

    async def async_set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        await self._client.set_state(FAN_MODE, fan_mode.capitalize())

    async def async_set_swing_mode(self, swing_mode):
        """Set new swing mode."""
        await self._client.set_swing(swing_mode.capitalize())

    async def async_turn_on(self):
        """Turn device on."""
        await self._client.set_state(OPERATION_MODE)

    async def async_turn_off(self):
        """Turn device off."""
        await self._client.set_state(ON_MODE, "off")
