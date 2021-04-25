"""Platform for climate integration."""
import logging

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


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""

    auth: Auth = hass.data[DOMAIN][config_entry.entry_id][AUTH_INSTANCE_KEY]
    said_list = auth.get_said_list()
    if not said_list:
        _LOGGER.debug("No appliances found")
        return

    aircon = AirConEntity(said_list[0], auth)
    async_add_entities([aircon], True)


class AirConEntity(ClimateEntity):
    """Representation of an air conditioner."""

    def __init__(self, said, auth: Auth):
        """Initialize the entity."""
        self._aircon = Aircon(auth, said, self.schedule_update_ha_state)

        self._name = said
        self._supported_features = (
            SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_SWING_MODE
        )

    async def async_added_to_hass(self) -> None:
        """Connect aircon to the cloud."""
        await self._aircon.connect()

        try:
            name = await self._aircon.fetch_name()
            if name is not None:
                self._name = name
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Failed to get name")

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return 16

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return 30

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._supported_features

    @property
    def name(self):
        """Return the name of the aircon."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._aircon.said

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._aircon.get_online()

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._aircon.get_current_temp()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._aircon.get_temp()

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

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

    @property
    def target_humidity_step(self):
        """Return the supported step of target humidity."""
        return 10

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self._aircon.set_humidity(humidity)

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return [HVAC_MODE_COOL, HVAC_MODE_HEAT, HVAC_MODE_FAN_ONLY, HVAC_MODE_OFF]

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, fan."""
        if not self._aircon.get_power_on():
            return HVAC_MODE_OFF

        mode: AirconMode = self._aircon.get_mode()
        if mode == AirconMode.Cool:
            return HVAC_MODE_COOL
        if mode == AirconMode.Heat:
            return HVAC_MODE_HEAT
        if mode == AirconMode.Fan:
            return HVAC_MODE_FAN_ONLY

        return None

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self._aircon.set_power_on(False)
            return

        mode = None
        if hvac_mode == HVAC_MODE_COOL:
            mode = AirconMode.Cool
        elif hvac_mode == HVAC_MODE_HEAT:
            mode = AirconMode.Heat
        elif hvac_mode == HVAC_MODE_FAN_ONLY:
            mode = AirconMode.Fan

        if not mode:
            _LOGGER.warning("Unexpected hvac mode")
            return

        await self._aircon.set_mode(mode)
        if not self._aircon.get_power_on():
            await self._aircon.set_power_on(True)

    @property
    def fan_modes(self):
        """List of available fan modes."""
        return [FAN_AUTO, FAN_HIGH, FAN_MEDIUM, FAN_LOW, FAN_OFF]

    @property
    def fan_mode(self):
        """Return the fan setting."""
        fanspeed = self._aircon.get_fanspeed()
        if fanspeed == AirconFanSpeed.Auto:
            return FAN_AUTO
        if fanspeed == AirconFanSpeed.Low:
            return FAN_LOW
        if fanspeed == AirconFanSpeed.Medium:
            return FAN_MEDIUM
        if fanspeed == AirconFanSpeed.High:
            return FAN_HIGH
        return FAN_OFF

    async def async_set_fan_mode(self, fan_mode):
        """Set fan mode."""
        fanspeed = None
        if fan_mode == FAN_AUTO:
            fanspeed = AirconFanSpeed.Auto
        elif fan_mode == FAN_LOW:
            fanspeed = AirconFanSpeed.Low
        elif fan_mode == FAN_MEDIUM:
            fanspeed = AirconFanSpeed.Medium
        elif fan_mode == FAN_HIGH:
            fanspeed = AirconFanSpeed.High
        if not fanspeed:
            return
        await self._aircon.set_fanspeed(fanspeed)

    @property
    def swing_modes(self):
        """List of available swing modes."""
        return [SWING_HORIZONTAL, SWING_OFF]

    @property
    def swing_mode(self):
        """Return the swing setting."""
        return SWING_HORIZONTAL if self._aircon.get_h_louver_swing() else SWING_OFF

    async def async_set_swing_mode(self, swing_mode):
        """Set new target temperature."""
        if swing_mode == SWING_HORIZONTAL:
            await self._aircon.set_h_louver_swing(True)
        else:
            await self._aircon.set_h_louver_swing(False)

    async def async_turn_on(self):
        """Turn device on."""
        await self._aircon.set_power_on(True)

    async def async_turn_off(self):
        """Turn device off."""
        await self._aircon.set_power_on(False)
