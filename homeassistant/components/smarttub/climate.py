"""Platform for climate integration."""
import logging

from smarttub import Spa

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_HEAT,
    PRESET_ECO,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.util.temperature import convert as convert_temperature

from .const import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP, DOMAIN, SMARTTUB_CONTROLLER
from .entity import SmartTubEntity

_LOGGER = logging.getLogger(__name__)

PRESET_DAY = "day"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up climate entity for the thermostat in the tub."""

    controller = hass.data[DOMAIN][entry.entry_id][SMARTTUB_CONTROLLER]

    entities = [
        SmartTubThermostat(controller.coordinator, spa) for spa in controller.spas
    ]

    async_add_entities(entities)


class SmartTubThermostat(SmartTubEntity, ClimateEntity):
    """The target water temperature for the spa."""

    PRESET_MODES = {
        Spa.HeatMode.AUTO: PRESET_NONE,
        Spa.HeatMode.ECONOMY: PRESET_ECO,
        Spa.HeatMode.DAY: PRESET_DAY,
    }

    HEAT_MODES = {v: k for k, v in PRESET_MODES.items()}

    HVAC_ACTIONS = {
        "OFF": CURRENT_HVAC_IDLE,
        "ON": CURRENT_HVAC_HEAT,
    }

    def __init__(self, coordinator, spa):
        """Initialize the entity."""
        super().__init__(coordinator, spa, "thermostat")

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        return self.HVAC_ACTIONS.get(self.spa_status.heater)

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_HEAT]

    @property
    def hvac_mode(self):
        """Return the current hvac mode.

        SmartTub devices don't seem to have the option of disabling the heater,
        so this is always HVAC_MODE_HEAT.
        """
        return HVAC_MODE_HEAT

    async def async_set_hvac_mode(self, hvac_mode: str):
        """Set new target hvac mode.

        As with hvac_mode, we don't really have an option here.
        """
        if hvac_mode == HVAC_MODE_HEAT:
            return
        raise NotImplementedError(hvac_mode)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        min_temp = DEFAULT_MIN_TEMP
        return convert_temperature(min_temp, TEMP_CELSIUS, self.temperature_unit)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        max_temp = DEFAULT_MAX_TEMP
        return convert_temperature(max_temp, TEMP_CELSIUS, self.temperature_unit)

    @property
    def supported_features(self):
        """Return the set of supported features.

        Only target temperature is supported.
        """
        return SUPPORT_PRESET_MODE | SUPPORT_TARGET_TEMPERATURE

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        return self.PRESET_MODES[self.spa_status.heat_mode]

    @property
    def preset_modes(self):
        """Return the available preset modes."""
        return list(self.PRESET_MODES.values())

    @property
    def current_temperature(self):
        """Return the current water temperature."""
        return self.spa_status.water.temperature

    @property
    def target_temperature(self):
        """Return the target water temperature."""
        return self.spa_status.set_temperature

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs[ATTR_TEMPERATURE]
        await self.spa.set_temperature(temperature)
        await self.coordinator.async_refresh()

    async def async_set_preset_mode(self, preset_mode: str):
        """Activate the specified preset mode."""
        heat_mode = self.HEAT_MODES[preset_mode]
        await self.spa.set_heat_mode(heat_mode)
        await self.coordinator.async_refresh()
