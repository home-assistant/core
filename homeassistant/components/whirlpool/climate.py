"""Platform for climate integration."""
import asyncio
import logging

import aiohttp
from whirlpool.aircon import Aircon, FanSpeed as AirconFanSpeed, Mode as AirconMode
from whirlpool.auth import Auth

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SWING_HORIZONTAL,
    SWING_OFF,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from .const import AUTH_INSTANCE_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)


AIRCON_MODE_MAP = {
    AirconMode.Cool: HVAC_MODE_COOL,
    AirconMode.Heat: HVAC_MODE_HEAT,
    AirconMode.Fan: HVAC_MODE_FAN_ONLY,
}

HVAC_MODE_TO_AIRCON_MODE = {v: k for k, v in AIRCON_MODE_MAP.items()}

AIRCON_FANSPEED_MAP = {
    AirconFanSpeed.Off: FAN_OFF,
    AirconFanSpeed.Auto: FAN_AUTO,
    AirconFanSpeed.Low: FAN_LOW,
    AirconFanSpeed.Medium: FAN_MEDIUM,
    AirconFanSpeed.High: FAN_HIGH,
}

FAN_MODE_TO_AIRCON_FANSPEED = {v: k for k, v in AIRCON_FANSPEED_MAP.items()}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    auth: Auth = hass.data[DOMAIN][config_entry.entry_id][AUTH_INSTANCE_KEY]
    said_list = auth.get_said_list()
    if not said_list:
        _LOGGER.debug("No appliances found")
        return

    # the whirlpool library needs to be updated to be able to support more
    # than one device, so we use only the first one for now
    aircon = AirConEntity(said_list[0], auth)
    async_add_entities([aircon], True)


class AirConEntity(ClimateEntity):
    """Representation of an air conditioner."""

    _attr_fan_modes = [FAN_AUTO, FAN_HIGH, FAN_MEDIUM, FAN_LOW, FAN_OFF]
    _attr_hvac_modes = [
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT,
        HVAC_MODE_FAN_ONLY,
        HVAC_MODE_OFF,
    ]
    _attr_max_temp = 30
    _attr_min_temp = 16
    _attr_supported_features = (
        SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_SWING_MODE
    )
    _attr_swing_modes = [SWING_HORIZONTAL, SWING_OFF]
    _attr_target_temperature_step = 1
    _attr_temperature_unit = TEMP_CELSIUS
    _attr_should_poll = False

    def __init__(self, said, auth: Auth):
        """Initialize the entity."""
        self._aircon = Aircon(auth, said, self.async_write_ha_state)

        self._attr_name = said
        self._attr_unique_id = said

    async def async_added_to_hass(self) -> None:
        """Connect aircon to the cloud."""
        await self._aircon.connect()

        try:
            name = await self._aircon.fetch_name()
            if name is not None:
                self._attr_name = name
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.exception("Failed to get name")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._aircon.get_online()

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._aircon.get_current_temp()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._aircon.get_temp()

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        await self._aircon.set_temp(kwargs.get(ATTR_TEMPERATURE))

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._aircon.get_current_humidity()

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._aircon.get_humidity()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self._aircon.set_humidity(humidity)

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, fan."""
        if not self._aircon.get_power_on():
            return HVAC_MODE_OFF

        mode: AirconMode = self._aircon.get_mode()
        return AIRCON_MODE_MAP.get(mode, None)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self._aircon.set_power_on(False)
            return

        mode = HVAC_MODE_TO_AIRCON_MODE.get(hvac_mode)
        if not mode:
            _LOGGER.warning("Unexpected hvac mode: %s", hvac_mode)
            return

        await self._aircon.set_mode(mode)
        if not self._aircon.get_power_on():
            await self._aircon.set_power_on(True)

    @property
    def fan_mode(self):
        """Return the fan setting."""
        fanspeed = self._aircon.get_fanspeed()
        return AIRCON_FANSPEED_MAP.get(fanspeed, FAN_OFF)

    async def async_set_fan_mode(self, fan_mode):
        """Set fan mode."""
        fanspeed = FAN_MODE_TO_AIRCON_FANSPEED.get(fan_mode)
        if not fanspeed:
            return
        await self._aircon.set_fanspeed(fanspeed)

    @property
    def swing_mode(self):
        """Return the swing setting."""
        return SWING_HORIZONTAL if self._aircon.get_h_louver_swing() else SWING_OFF

    async def async_set_swing_mode(self, swing_mode):
        """Set new target temperature."""
        await self._aircon.set_h_louver_swing(swing_mode == SWING_HORIZONTAL)

    async def async_turn_on(self):
        """Turn device on."""
        await self._aircon.set_power_on(True)

    async def async_turn_off(self):
        """Turn device off."""
        await self._aircon.set_power_on(False)
