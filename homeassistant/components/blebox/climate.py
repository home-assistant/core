"""BleBox climate entity implementation."""

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS

from . import CommonEntity, async_add_blebox


# TODO: remove?
async def async_setup_platform(hass, config, async_add, discovery_info=None):
    """Set up BleBox platform."""
    # TODO: coverage
    return await async_add_blebox(
        BleBoxClimateEntity, "climates", hass, config, async_add
    )


async def async_setup_entry(hass, config_entry, async_add):
    """Set up a BleBox entry."""
    return await async_add_blebox(
        BleBoxClimateEntity, "climates", hass, config_entry.data, async_add,
    )


class BleBoxClimateEntity(CommonEntity, ClimateDevice):
    """Representation of a BleBox climate feature (saunaBox)."""

    @property
    def supported_features(self):
        """Return the supported climate features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def hvac_mode(self):
        """Return the desired HVAC mode."""
        return {None: None, False: HVAC_MODE_OFF, True: HVAC_MODE_HEAT}[
            self._feature.is_on
        ]

    @property
    def hvac_action(self):
        """Return the actual current HVAC action."""
        is_on = self._feature.is_on
        if not is_on:
            return None if is_on is None else CURRENT_HVAC_OFF

        states = {None: None, False: CURRENT_HVAC_IDLE, True: CURRENT_HVAC_HEAT}

        heating = self._feature.is_heating
        return states[heating]

    @property
    def hvac_modes(self):
        """Return a list of possible HVAC modes."""
        return (HVAC_MODE_OFF, HVAC_MODE_HEAT)

    @property
    def temperature_unit(self):
        """Return the temperature unit."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._feature.current

    @property
    def target_temperature(self):
        """Return the desired thermostat temperature."""
        return self._feature.desired

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the climate entity mode."""
        if hvac_mode == HVAC_MODE_OFF:
            return await self._feature.async_off()

        if hvac_mode == HVAC_MODE_HEAT:
            return await self._feature.async_on()

        raise NotImplementedError

    async def async_set_temperature(self, **kwargs):
        """Set the thermostat temperature."""
        value = kwargs[ATTR_TEMPERATURE]
        await self._feature.async_set_temperature(value)
