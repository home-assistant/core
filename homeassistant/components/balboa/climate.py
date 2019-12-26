"""Support for Balboa Spa Wifi adaptor."""
import logging
from typing import List

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    PRECISION_HALVES,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

# from pybalboa import BalboaSpaWifi
from . import BalboaEntity
from .const import (
    CLIMATE_SUPPORTED_FANSTATES,
    CLIMATE_SUPPORTED_MODES,
    DOMAIN as BALBOA_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up of the spa is done through async_setup_entry."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the spa climate device."""
    spa = hass.data[BALBOA_DOMAIN][entry.entry_id]
    name = entry.data[CONF_NAME]
    devs = []
    devs.append(BalboaSpaClimate(hass, spa, name))
    async_add_entities(devs, True)


class BalboaSpaClimate(BalboaEntity, ClimateDevice):
    """Representation of a Balboa Spa Climate device."""

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

        if self._client.have_blower():
            features |= SUPPORT_FAN_MODE

        return features

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of supported HVAC modes."""
        return CLIMATE_SUPPORTED_MODES

    @property
    def hvac_mode(self) -> str:
        """Return the current HVAC mode."""
        mode = self._client.get_heatmode()
        if mode == self._client.HEATMODE_READY:
            return HVAC_MODE_HEAT
        if mode == self._client.HEATMODE_RNR:
            return HVAC_MODE_AUTO
        return HVAC_MODE_OFF

    @property
    def hvac_action(self) -> str:
        """Return the current operation mode."""
        state = self._client.get_heatstate()
        if state == self._client.ON:
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

    @property
    def fan_modes(self) -> List[str]:
        """Return the list of available fan modes."""
        return CLIMATE_SUPPORTED_FANSTATES

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode."""
        fanmode = self._client.get_blower()
        if fanmode is None:
            return FAN_OFF
        if fanmode == self._client.BLOWER_OFF:
            return FAN_OFF
        if fanmode == self._client.BLOWER_LOW:
            return FAN_LOW
        if fanmode == self._client.BLOWER_MEDIUM:
            return FAN_MEDIUM
        if fanmode == self._client.BLOWER_HIGH:
            return FAN_HIGH

    @property
    def name(self):
        """Return the name of the spa."""
        return f"{self._name}"

    @property
    def precision(self):
        """Return the precision of the system.

        Balboa spas return data in C or F depending on how the display is set,
        because ultimately, we are just reading the display.
        In C, we have half-degree accuracy, in F, whole degree.
        """
        tscale = self._client.get_tempscale()
        if tscale == self._client.TSCALE_C:
            return PRECISION_HALVES
        return PRECISION_WHOLE

    @property
    def temperature_unit(self):
        """Return the unit of measurement, as defined by the API."""
        tscale = self._client.get_tempscale()
        if tscale == self._client.TSCALE_C:
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._client.get_curtemp()

    @property
    def target_temperature(self):
        """Return the target temperature we try to reach."""
        return self._client.get_settemp()

    @property
    def min_temp(self) -> int:
        """Return the minimum temperature supported by the spa."""
        trange = self._client.get_temprange()
        scale = self._client.get_tempscale()
        return self._client.tmin[trange][scale]

    @property
    def max_temp(self) -> int:
        """Return the minimum temperature supported by the spa."""
        trange = self._client.get_temprange()
        scale = self._client.get_tempscale()
        return self._client.tmax[trange][scale]

    @property
    def preset_modes(self):
        """Return the valid preset modes."""
        return self._client.get_heatmode_stringlist()

    @property
    def preset_mode(self):
        """Return current preset mode."""
        return self._client.get_heatmode(True)

    async def async_set_temperature(self, **kwargs):
        """Set a new target temperature."""
        await self._client.send_temp_change(int(kwargs[ATTR_TEMPERATURE]))

    async def async_set_preset_mode(self, preset_mode) -> None:
        """Set new preset mode."""
        modelist = self._client.get_heatmode_stringlist()
        if preset_mode in modelist:
            await self._client.change_heatmode(modelist.index(preset_mode))

    async def async_set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        if fan_mode == FAN_OFF:
            await self._client.change_blower(self._client.BLOWER_OFF)
        elif fan_mode == FAN_LOW:
            await self._client.change_blower(self._client.BLOWER_LOW)
        elif fan_mode == FAN_MEDIUM:
            await self._client.change_blower(self._client.BLOWER_MEDIUM)
        elif fan_mode == FAN_HIGH:
            await self._client.change_blower(self._client.BLOWER_HIGH)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode.

        OFF = REST
        AUTO = READY_IN_REST
        HEAT = READY
        """
        if hvac_mode == HVAC_MODE_HEAT:
            await self._client.change_heatmode(self._client.HEATMODE_READY)
        elif hvac_mode == HVAC_MODE_OFF:
            await self._client.change_heatmode(self._client.HEATMODE_REST)
        elif hvac_mode == HVAC_MODE_AUTO:
            await self._client.change_heatmode(self._client.HEATMODE_RNR)
